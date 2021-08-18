import json
import dateutil.parser
import pytz
from datetime import datetime
import re
from .utils import get_stream_from_s3body


try:
    JSONParseException = json.decoder.JSONDecodeError
except AttributeError:  # Python 2
    JSONParseException = ValueError


class CloudtrailCollector(object):
    MAX_S3_DELETES = 999

    def __init__(self, bucket_name, account_id, session, agent, log):
        self.bucket_name = bucket_name
        self.session = session
        self.agent = agent
        self.account_id = account_id
        self.log = log

    def get_messages(self, not_before):
        try:
            # try s3
            return self._get_messages_from_s3(not_before)
        except Exception as e:
            self.log.exception(e)
            self.log.info("Collecting EventBridge events from S3 failed, falling back to CloudTrail history")
            # try loopup_events
            self.agent.warning("Falling back to slower Cloudtrail lookup_events")
            return self._get_messages_from_cloudtrail(not_before)

    def _get_bucket_name(self):
        if self.bucket_name:
            return self.bucket_name
        else:
            return "stackstate-logs-{}".format(self.account_id)

    def check_bucket(self, client, bucket_name):
        versioning = client.get_bucket_versioning(Bucket=bucket_name)
        return isinstance(versioning, dict) and versioning.get("Status") == "Enabled"

    def _get_messages_from_s3(self, not_before):
        client = self.session.client("s3")
        region = client.meta.region_name
        bucket_name = self._get_bucket_name()
        if not self.check_bucket(client, bucket_name):
            raise Exception("Object versioning must be enabled on the bucket")
        self.log.info("Start collecting EventBridge events from S3 bucket {} for region {}".format(bucket_name, region))
        to_delete = []
        files_to_handle = []
        for pg in client.get_paginator("list_objects_v2").paginate(
            Bucket=bucket_name, Prefix="AWSLogs/{act}/EventBridge/{rgn}/".format(act=self.account_id, rgn=region)
        ):
            contents = pg.get("Contents") or []
            self.log.info("Found {} objects in the S3 bucket".format(len(contents)))
            for itm in contents:
                # get the datetime from the objects key
                key_regex = r"(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})-(?P<h>\d{2})-(?P<mm>\d{2})-(?P<s>\d{2})"
                pts = re.search(key_regex, itm.get("Key", ""))
                if pts:
                    pts = pts.groupdict()
                    dt = datetime(
                        int(pts["y"]), int(pts["m"]), int(pts["d"]), int(pts["h"]), int(pts["mm"]), int(pts["s"])
                    ).replace(tzinfo=pytz.utc)
                    if dt < not_before:
                        to_delete.append({"Key": itm["Key"]})
                        if len(to_delete) > self.MAX_S3_DELETES:
                            self._delete_files(client, bucket_name, to_delete)
                            to_delete = []
                    else:
                        files_to_handle.append(itm["Key"])

        self._delete_files(client, bucket_name, to_delete)
        return self._process_files(client, bucket_name, files_to_handle)

    def _get_messages_from_cloudtrail(self, not_before):
        client = self.session.client("cloudtrail")
        # collect the events (ordering is most recent event first)
        self.log.info("Start collecting EventBridge events from CloudTrail history (can have 15 minutes delay)")
        for pg in client.get_paginator("lookup_events").paginate(
            LookupAttributes=[{"AttributeKey": "ReadOnly", "AttributeValue": "false"}],
        ):
            for itm in pg.get("Events") or []:
                rec = json.loads(itm["CloudTrailEvent"])
                event_date = dateutil.parser.isoparse(rec["eventTime"])
                if event_date > not_before:
                    yield rec

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

    def _process_files(self, client, bucket_name, files):
        self.log.info("Starting processing of {} S3 objects".format(len(files)))
        for file in reversed(files):
            self.log.info("Starting processing of object {}".format(file))
            objects = []
            s3_body = client.get_object(Bucket=bucket_name, Key=file).get("Body")
            with get_stream_from_s3body(s3_body) as data:
                decoder = json.JSONDecoder()
                txt = data.read().decode("ascii")
                while txt:
                    try:
                        obj, index = decoder.raw_decode(txt)
                        txt = txt[index:]
                        msg_type = obj.get("detail-type", "")
                        detail = obj.get("detail", {})
                        if msg_type == "EC2 Instance State-change Notification":
                            detail["eventSource"] = "ec2.amazonaws.com"
                            detail["eventName"] = "InstanceStateChangeNotification"
                        if detail:
                            objects.append(obj["detail"])
                    except JSONParseException:
                        txt = ""
            self.log.info("Object {} contained {} events".format(file, len(objects)))
            for event in reversed(objects):
                yield event
            self._delete_files(client, bucket_name, [{"Key": file}])
