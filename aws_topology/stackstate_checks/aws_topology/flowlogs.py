import gzip
import botocore
import io
import pytz
from datetime import datetime
from six import PY2, string_types
import re
from .resources import is_private, ip_version, client_array_operation, make_valid_data
from schematics import Model
from schematics.types import StringType, ListType, ModelType
import json


class Ipv6Address(Model):
    Ipv6Address = StringType(default="unknown_ipv6")


selflog = None

class NetworkInterface(Model):
    NetworkInterfaceId = StringType(required=True)
    PrivateIpAddress = StringType(default="unknown_ipv4")
    Ipv6Addresses = ListType(ModelType(Ipv6Address), default=[])
    VpcId = StringType(default="unknown_vpc")
    Description = StringType(default="")

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
    for id, itf in connection.network_interfaces.items():
        if itf.Description.startswith("Interface for NAT Gateway") \
            or itf.Description.startswith("ELB app/"):
            result = False
    return result


class Connection(object):
    def __init__(self, namespace, family, laddr, raddr, start, end, traffic_type, incoming, byte_count, nwitf):
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
        self.add_traffic(start, end, traffic_type, incoming, byte_count, nwitf, False)

    def add_traffic(self, start, end, traffic_type, incoming, byte_count, nwitf, reverse):
        # TODO because now the id uses sorted ips we sometimes need to reverse the traffic
        # keeping this arround, has all ip addresses of network interface
        self.network_interfaces[nwitf.NetworkInterfaceId] = nwitf
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
    def bytes_sent_per_second(self):
        try:
            return self.bytes_sent / self.interval_seconds
        finally:
            return 0.0

    @property
    def bytes_received_per_second(self):
        try:
            return self.bytes_received / self.interval_seconds
        finally:
            return 0.0


class FlowlogCollector(object):
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

    def read_flowlog(self, not_before):
        nwinterfaces = self.collect_networkinterfaces()
        client = self.session.client("s3")
        region = client.meta.region_name
        bucket_name = self._get_bucket_name()
        self.log.info("Start collecting FlowLogs events from S3 bucket {} for region {}".format(bucket_name, region))
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
        self.log.info("Found {} objects in S3".format(len(files_to_handle)))
        connections = self.process_files(client, bucket_name, files_to_handle, nwinterfaces)
        self.log.info("Found {} connections in FlowLogs".format(len(connections.keys())))
        self.process_connections(connections)

    def _delete_files(self, client, bucket_name, files):
        for i in range(0, len(files), self.MAX_S3_DELETES):
            try:
                self.log.info(
                    "Deleting {} files from S3 bucket {}".format(len(files[i : i + self.MAX_S3_DELETES]), bucket_name)
                )
                client.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": files[i : i + self.MAX_S3_DELETES], "Quiet": True},
                )
            except Exception as e:
                self.log.exception(e)
                self.agent.warning("CloudtrailCollector: Deleting s3 files failed")

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
        if src_ip in nwitf.addresses:
            laddr = "{}:{}".format(src_ip, src_port)
            raddr = "{}:{}".format(dst_ip, dst_port)
            private = is_private(dst_ip)
            dir = "out"
        elif dst_ip in nwitf.addresses:
            laddr = "{}:{}".format(dst_ip, dst_port)
            raddr = "{}:{}".format(src_ip, src_port)
            private = is_private(src_ip)
            dir = "in"
        else:
            self.log.warning("Could not determine traffic direction src={} dst={}".format(src_ip, dst_ip))

        if private and dir != "unknown":  # currently only supporting private traffic
            id, reverse = connection_identifier(nwitf.VpcId, dst_ip, src_ip)
            conn = connections.get(id, None)
            if conn:
                conn.add_traffic(start, end, protocol, dir == "in", bytes_transfered, nwitf, reverse)
            else:
                connections[id] = Connection(
                    nwitf.VpcId, family, laddr, raddr, start, end, protocol, dir == "in", bytes_transfered, nwitf
                )

    def process_files(self, client, bucket_name, files, nwinterfaces):
        connections = {}
        for file in files:
            s3_body = client.get_object(Bucket=bucket_name, Key=file).get("Body")
            self._delete_files(client, bucket_name, [{"Key": file}])
            with self._get_stream(s3_body) as data:
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
                        if status != "NODATA" and status != "SKIPDATA" and nwitf:
                            self.process_record(connections, log, nwitf)
                else:
                    self.log.warning("Flowlog had unsupported format")
        return connections

    def process_connection(self, id, connection):
        # create component for local side
        ip = connection.laddr.split(":")[0]
        lcid = "local/{}".format(id)
        self.agent.component(
            self.location_info,
            lcid,
            "vpc.request",
            {"URN": ["urn:vpcip:{}/{}".format(connection.namespace, ip)]},
        )
        self.log.info("LEFT " + "urn:vpcip:{}/{}".format(connection.namespace, ip))
        # remote component for remote side
        ip = connection.raddr.split(":")[0]
        rcid = "remote/{}".format(id)
        self.agent.component(
            self.location_info,
            rcid,
            "vpc.request",
            {"URN": ["urn:vpcip:{}/{}".format(connection.namespace, ip)]},
        )
        self.log.info("RIGHT " + "urn:vpcip:{}/{}".format(connection.namespace, ip))
        # make relation between the two
        data = {
            "traffic_type": connection.traffic_type,
            "bytes_sent": connection.bytes_sent,
            "bytes_received": connection.bytes_received,
            "family": connection.family,
            "bytes_sent_per_second": str(connection.bytes_sent_per_second),
            "bytes_received_per_second": str(connection.bytes_received_per_second),
            "local_address": connection.laddr,
            "remote_address": connection.raddr
        }
        network_interfaces = []
        self.log.info(json.dumps(data, indent=2, default=str))
        for id, itf in connection.network_interfaces.items():
            network_interfaces.append(itf.original_data)
        data["network_interfaces"] = network_interfaces
        self.agent.relation(lcid, rcid, "is-connected-to", data)

    def process_connections(self, connections):
        for id, connection in connections.items():
            if should_process(connection):
                self.process_connection(id, connection)

    def _is_gz_file(self, body):
        with io.BytesIO(body) as test_f:
            return test_f.read(2) == b"\x1f\x8b"

    def _get_stream(self, body):
        if isinstance(body, string_types):
            # this case is only for test purposes
            if PY2:
                body = bytes(body)
            else:
                body = bytes(body, "ascii")
        elif isinstance(body, botocore.response.StreamingBody):
            body = body.read()
        if self._is_gz_file(body):
            return gzip.GzipFile(fileobj=io.BytesIO(body), mode="rb")
        else:
            return io.BytesIO(body)

    def _get_bucket_name(self):
        if self.bucket_name:
            return self.bucket_name
        else:
            return "stackstate-logs-{}".format(self.account_id)
