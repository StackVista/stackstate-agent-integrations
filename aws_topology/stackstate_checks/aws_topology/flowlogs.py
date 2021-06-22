import gzip
import botocore
import io
import pytz
from datetime import datetime
from six import PY2, string_types
import re
from .resources import is_private, client_array_operation


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
        client = self.session.client('ec2')
        for itf in client_array_operation(
            client,
            "describe_network_interfaces",
            "NetworkInterfaces"
        ):
            nwinterfaces[itf["NetworkInterfaceId"]] = itf
        return nwinterfaces

    def read_flowlog(self, not_before):
        nwinterfaces = self.collect_networkinterfaces()
        client = self.session.client('s3')
        region = client.meta.region_name
        bucket_name = self._get_bucket_name()
        to_delete = []
        files_to_handle = []
        for pg in client.get_paginator('list_objects_v2').paginate(
            Bucket=bucket_name,
            Prefix='AWSLogs/{act}/vpcflowlogs/{rgn}/'.format(
                act=self.account_id,
                rgn=region
            )
        ):
            for itm in pg.get('Contents') or []:
                key_regex = r"(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})T(?P<h>\d{2})(?P<mm>\d{2})Z"
                pts = re.search(key_regex, itm.get("Key", ""))
                if pts:
                    pts = pts.groupdict()
                    dt = datetime(
                        int(pts["y"]), int(pts["m"]), int(pts["d"]), int(pts["h"]), int(pts["mm"]), 0
                    ).replace(tzinfo=pytz.utc)
                    if dt < not_before:
                        to_delete.append({
                            'Key': itm['Key']
                        })
                        if len(to_delete) > self.MAX_S3_DELETES:
                            self._delete_files(client, bucket_name, to_delete)
                            to_delete = []
                    else:
                        files_to_handle.append(itm['Key'])

        self._delete_files(client, bucket_name, to_delete)
        return self.process_files(client, bucket_name, files_to_handle, nwinterfaces)

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

    def process_files(self, client, bucket_name, files, nwinterfaces):
        traffic = {}
        for file in files:
            s3_body = client.get_object(Bucket=bucket_name, Key=file).get('Body')
            self._delete_files(client, bucket_name, [{"Key": file}])
            with self._get_stream(s3_body) as data:
                first = True
                for line in data:
                    line = line.decode('ascii').strip()
                    if first:
                        first = False
                        flds = line.split(' ')
                    else:
                        vals = line.split(' ')
                        log = {fld: val for (fld, val) in zip(flds, vals)}
                        if log.get('log-status', 'NODATA') != 'NODATA':
                            nwitf = nwinterfaces.get(log["interface-id"], None)
                            pip = nwitf["PrivateIpAddress"]
                            dir = "unknown"
                            ip = traffic.get(pip)
                            if ip is None:
                                ip = traffic[pip] = {"in": {}, "out": {}, "vpc": nwitf["VpcId"]}
                            private = None
                            other_ip = ""
                            if pip == log["srcaddr"]:
                                other_ip = log["dstaddr"]
                                private = is_private(other_ip)
                                dir = "out"
                            elif pip == log["dstaddr"]:
                                other_ip = log["srcaddr"]
                                private = is_private(other_ip)
                                dir = "in"
                            if private:
                                rec = ip.get(dir, {}).get(other_ip)
                                if not rec:
                                    res = {
                                        "packets": int(log["packets"]),
                                        "bytes": int(log["bytes"])
                                    }
                                    ip[dir][other_ip] = res
                                else:
                                    res["bytes"] += int(log["bytes"])
                                    res["packets"] += int(log["packets"])

        # process traffic
        connections = set()

        def add_to_connections(vpc_id, ip1, ip2):
            if ip1 > ip2:
                connections.add("urn:vpcip:{}/{}".format(vpc_id, ip2) + '|' + "urn:vpcip:{}/{}".format(vpc_id, ip1))
            else:
                connections.add("urn:vpcip:{}/{}".format(vpc_id, ip1) + '|' + "urn:vpcip:{}/{}".format(vpc_id, ip2))

        for nwi in traffic:
            for ip in traffic[nwi]["in"]:
                add_to_connections(traffic[nwi]["vpc"], nwi, ip)
            for ip in traffic[nwi]["out"]:
                add_to_connections(traffic[nwi]["vpc"], nwi, ip)
        for connection in connections:
            sides = connection.split('|')
            self.agent.component(self.location_info, sides[0], 'vpc.request', {"URN": [sides[0]]})
            self.agent.component(self.location_info, sides[1], 'vpc.request', {"URN": [sides[1]]})
            self.agent.relation(sides[0], sides[1], "uses service", {})

    def _is_gz_file(self, body):
        with io.BytesIO(body) as test_f:
            return test_f.read(2) == b'\x1f\x8b'

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
            return gzip.GzipFile(fileobj=io.BytesIO(body), mode='rb')
        else:
            return io.BytesIO(body)

    def _get_bucket_name(self):
        if self.bucket_name:
            return self.bucket_name
        else:
            return "stackstate-logs-{}".format(self.account_id)
