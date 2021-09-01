import re
from datetime import datetime

import pytz
from schematics import Model
from schematics.types import StringType, ListType, ModelType

from .resources import is_private, ip_version, client_array_operation, make_valid_data, ipaddress_to_urn
from .utils import get_stream_from_s3body


class Ipv6Address(Model):
    Ipv6Address = StringType(default="unknown_ipv6")


class Association(Model):
    PublicIp = StringType()


class NetworkInterface(Model):
    NetworkInterfaceId = StringType(required=True)
    PrivateIpAddress = StringType(default="unknown_ipv4")
    Ipv6Addresses = ListType(ModelType(Ipv6Address), default=[])
    VpcId = StringType(default="unknown_vpc")
    Description = StringType(default="")
    Association = ModelType(Association)

    addresses = set()

    def __init__(self, raw_data=None, *args, **kwargs):
        self.original_data = make_valid_data(raw_data)
        kwargs["raw_data"] = raw_data
        super(NetworkInterface, self).__init__(*args, **kwargs)


def connection_identifier(namespace, src, dst):
    if src < dst:
        return "{}/{}/{}".format(namespace, src, dst), False
    else:
        return "{}/{}/{}".format(namespace, dst, src), True


def should_process(connection):
    # filter out if any of the network_interfaces starts with "Interface for NAT Gateway" or "ELB app/"
    result = True
    for _, itf in connection.network_interfaces.items():
        if itf.Description.startswith("Interface for NAT Gateway") or itf.Description.startswith("ELB app/"):
            result = False
    return result


class Connection(object):
    def __init__(self, namespace, family, laddr, raddr, start, end, traffic_type, incoming, byte_count, nwitf, log):
        self.namespace = namespace
        self.laddr = laddr
        self.raddr = raddr
        self.family = family
        self.traffic_type = str(traffic_type)
        self.start_time = start
        self.end_time = end
        self.bytes_sent = 0
        self.bytes_received = 0
        self.network_interfaces = {}
        self.traffic_log = []  # for debugging purposes
        self.add_traffic(start, end, traffic_type, incoming, byte_count, nwitf, False, log)

    def add_traffic(self, start, end, traffic_type, incoming, byte_count, nwitf, reverse, log):
        self.network_interfaces.update(nwitf)
        _, itf = next(iter(nwitf.items()))
        self.traffic_log.append("nwitf: {} log: {} incoming={} reverse={}".format(
            itf.PrivateIpAddress,
            log,
            incoming,
            reverse
        ))
        if self.start_time == 0 or start < self.start_time:
            self.start_time = start
        if self.end_time == 0 or end > self.end_time:
            self.end_time = end
        if incoming ^ reverse:
            self.bytes_received += byte_count
        else:
            self.bytes_sent += byte_count
        if str(traffic_type) != self.traffic_type:
            self.traffic_type = "unknown"

    @property
    def interval_seconds(self):
        return self.end_time - self.start_time

    @property
    def total_bytes_sent(self):
        """
        We are dividing send bytes by 2 because all private traffic in a VPC is counted twice.
        Once for each network interface since each reports in and out.
        """
        return self.bytes_sent / 2

    @property
    def total_bytes_received(self):
        """
        We are dividing received bytes by 2 because all private traffic in a VPC is counted twice.
        Once for each network interface since each reports in and out.
        """
        return self.bytes_received / 2

    @property
    def bytes_sent_per_second(self):
        try:
            return (0.0 + self.total_bytes_sent) / self.interval_seconds
        except Exception:
            return 0.0

    @property
    def bytes_received_per_second(self):
        try:
            return (0.0 + self.total_bytes_received) / self.interval_seconds
        except Exception:
            return 0.0


class FlowLogCollector(object):
    MAX_S3_DELETES = 999

    def __init__(self, bucket_name, account_id, session, location_info, agent, log):
        self.bucket_name = bucket_name
        self.session = session
        self.location_info = location_info
        self.agent = agent
        self.account_id = account_id
        self.log = log

    def collect_networkinterfaces(self):
        nwinterfaces = {}
        client = self.session.client("ec2")
        for raw_itf in client_array_operation(client, "describe_network_interfaces", "NetworkInterfaces"):
            itf = NetworkInterface(raw_itf, strict=False)
            # get all ip addresses bound to this interface
            addresses = {itf.PrivateIpAddress}
            for ipv6 in itf.Ipv6Addresses:
                addresses.add(ipv6.Ipv6Address)
            itf.addresses = addresses
            nwinterfaces[itf.NetworkInterfaceId] = itf
        return nwinterfaces

    @staticmethod
    def check_bucket(client, bucket_name):
        versioning = client.get_bucket_versioning(Bucket=bucket_name)
        return isinstance(versioning, dict) and versioning.get("Status") == "Enabled"

    def read_flowlog(self, not_before):
        nwinterfaces = self.collect_networkinterfaces()
        client = self.session.client("s3")
        region = client.meta.region_name
        bucket_name = self._get_bucket_name()
        if not self.check_bucket(client, bucket_name):
            raise Exception("Object versioning must be enabled on the bucket")
        self.log.info("Start FlowLogs for {} from S3-bucket {}".format(bucket_name, region))
        to_delete = []
        files_to_handle = []
        for pg in client.get_paginator("list_objects_v2").paginate(
                Bucket=bucket_name, Prefix="AWSLogs/{act}/vpcflowlogs/{rgn}/".format(act=self.account_id, rgn=region)
        ):
            for itm in pg.get("Contents") or []:
                # regex extracts datetime y, m, d, h and m from the object name into named groups
                key_regex = r"(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})T(?P<h>\d{2})(?P<mm>\d{2})Z"
                pts = re.search(key_regex, itm.get("Key", ""))
                if pts:
                    pts = pts.groupdict()
                    dt = datetime(
                        int(pts["y"]), int(pts["m"]), int(pts["d"]), int(pts["h"]), int(pts["mm"]), 0
                    ).replace(tzinfo=pytz.utc)
                    if dt < not_before:
                        to_delete.append({"Key": itm["Key"]})
                        if len(to_delete) > self.MAX_S3_DELETES:
                            self._delete_files(client, bucket_name, to_delete)
                            to_delete = []
                    else:
                        files_to_handle.append(itm["Key"])

        self._delete_files(client, bucket_name, to_delete)
        number_of_files = len(files_to_handle)
        if number_of_files > 0:
            connections = self.process_files(client, bucket_name, files_to_handle, nwinterfaces)
            count = self.process_connections(connections)
            self.log.info("Found {} S3 objects with {} connections".format(number_of_files, count))

    def _delete_files(self, client, bucket_name, files):
        for i in range(0, len(files), self.MAX_S3_DELETES):
            try:
                self.log.info(
                    "Deleting {} files from S3 bucket {}".format(len(files[i: i + self.MAX_S3_DELETES]), bucket_name)
                )
                client.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": files[i: i + self.MAX_S3_DELETES], "Quiet": True},
                )
            except Exception as e:
                self.log.exception(e)
                self.agent.warning("FlowLogCollector: Deleting s3 files failed")

    def process_record(self, connections, log, nwitf):
        src_ip = log["srcaddr"]
        dst_ip = log["dstaddr"]
        src_port = log["srcport"]
        dst_port = log["dstport"]
        start = int(log.get("start", "0"))
        end = int(log.get("end", "0"))
        protocol = log.get("protocol", "unknown_protocol")
        bytes_transfered = int(log.get("bytes", "0"))
        dir = "unknown"
        private = None
        family = "v4" if ip_version(src_ip) == 4 else "v6"
        nwitf_update = {}
        id = ""
        reverse = None
        if src_ip in nwitf.addresses:
            laddr = "{}:{}".format(src_ip, src_port)
            raddr = "{}:{}".format(dst_ip, dst_port)
            private = is_private(dst_ip)
            dir = "out"
            nwitf_update = {src_ip: nwitf}
            id, reverse = connection_identifier(nwitf.VpcId, src_ip, dst_ip)
        elif dst_ip in nwitf.addresses:
            laddr = "{}:{}".format(dst_ip, dst_port)
            raddr = "{}:{}".format(src_ip, src_port)
            private = is_private(src_ip)
            dir = "in"
            nwitf_update = {dst_ip: nwitf}
            id, reverse = connection_identifier(nwitf.VpcId, dst_ip, src_ip)
        else:
            self.log.warning("Could not determine traffic direction src={} dst={}".format(src_ip, dst_ip))
            return

        if private and dir != "unknown":  # currently only supporting private traffic
            logline = "{}:{} <-> {}:{} bytes={}".format(src_ip, src_port, dst_ip, dst_port, bytes_transfered)
            conn = connections.get(id, None)
            if conn:
                conn.add_traffic(start, end, protocol, dir == "in", bytes_transfered, nwitf_update, reverse, logline)
            else:
                connections[id] = Connection(
                    nwitf.VpcId,
                    family,
                    laddr,
                    raddr,
                    start,
                    end,
                    protocol,
                    dir == "in",
                    bytes_transfered,
                    nwitf_update,
                    logline
                )

    def process_files(self, client, bucket_name, files, nwinterfaces):
        connections = {}
        for file in files:
            s3_body = client.get_object(Bucket=bucket_name, Key=file).get("Body")
            self._delete_files(client, bucket_name, [{"Key": file}])
            with get_stream_from_s3body(s3_body) as data:
                lines = iter(data)
                flds = next(lines).decode("ascii").strip().split(" ")
                if set(flds) >= set(
                        ("srcaddr", "dstaddr", "srcport", "dstport", "interface-id", "protocol", "start", "end")
                ):
                    for line in lines:
                        line = line.decode("ascii").strip()
                        vals = line.split(" ")
                        log = {fld: val for (fld, val) in zip(flds, vals)}
                        status = log.get("log-status", "NODATA")
                        nwitf = nwinterfaces.get(log["interface-id"], None)
                        # TODO there is the log record also contains "action" (ACCEPT or REJECT)
                        if status != "NODATA" and status != "SKIPDATA" and nwitf:
                            self.process_record(connections, log, nwitf)
                else:
                    self.log.warning("Flow log had unsupported format")
        return connections

    def process_connection(self, id, connection):
        network_interfaces = []
        for _, itf in connection.network_interfaces.items():
            network_interfaces.append(itf.original_data)
        data = {
            "traffic_type": connection.traffic_type,
            "bytes_sent": connection.total_bytes_sent,
            "bytes_received": connection.total_bytes_received,
            "family": connection.family,
            "bytes_sent_per_second": connection.bytes_sent_per_second,
            "bytes_received_per_second": connection.bytes_received_per_second,
            "local_address": connection.laddr,
            "remote_address": connection.raddr,
            "log": connection.traffic_log,
            "network_interfaces": network_interfaces,
        }
        data = make_valid_data(data)
        # create component for local side
        ip = connection.laddr.split(":")[0]
        nwitf = connection.network_interfaces.get(ip, None)
        lcid = "local/{}".format(id)
        urns = [ipaddress_to_urn(ip, connection.namespace)]
        if nwitf and nwitf.Association and nwitf.Association.PublicIp:
            urns.append(ipaddress_to_urn(nwitf.Association.PublicIp, ""))
        self.agent.component(
            self.location_info,
            lcid,
            "vpc.request",
            {"URN": urns, "debug_data": data},
        )
        # remote component for remote side
        ip = connection.raddr.split(":")[0]
        nwitf = connection.network_interfaces.get(ip, None)
        rcid = "remote/{}".format(id)
        urns = [ipaddress_to_urn(ip, connection.namespace)]
        if nwitf and nwitf.Association and nwitf.Association.PublicIp:
            urns.append(ipaddress_to_urn(nwitf.Association.PublicIp, ""))
        self.agent.component(
            self.location_info,
            rcid,
            "vpc.request",
            {"URN": urns, "debug_data": data},
        )
        # make relation between the two
        self.agent.relation(lcid, rcid, "flowlog", data)

    def process_connections(self, connections):
        count = 0
        for id, connection in connections.items():
            if should_process(connection):
                self.process_connection(id, connection)
                count += 1
        return count

    def _get_bucket_name(self):
        if self.bucket_name:
            return self.bucket_name
        else:
            return "stackstate-logs-{}".format(self.account_id)
