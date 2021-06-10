from .resources.registry import RegisteredResourceCollector
import json
import dateutil.parser
import pytz
from datetime import datetime
import gzip
import io


class CloudtrailCollector(object):
    def __init__(self, bucket_name, account_id, session, agent):
        self.bucket_name = bucket_name
        self.session = session
        self.agent = agent
        self.account_id = account_id

    def get_messages(self, not_before):
        try:
            # try s3
            return self._get_messages_from_s3()
        except Exception as e:
            # try loopup_events
            return self._get_messages_from_cloudtrail(not_before)

    def _get_bucket_name(self):
        if self.bucket_name:
            return self.bucket_name
        else:
            return 'stackstate-logs-{}'.format(self.account_id)

    def _get_messages_from_s3(self, not_before):
        client = self.session.client('s3')
        region = client.meta.region_name
        bucket_name = self._get_bucket_name()
        to_delete = []
        files_to_handle = []
        for pg in client.get_paginator('list_objects_v2').paginate(
            Bucket=bucket_name,
            Prefix='AWSLogs/{act}/EventBridge/{rgn}/'.format(
                act=self.account_id,
                rgn=region
            )
        ):
            for itm in pg.get('Contents') or []:
                pts = [int(i) for i in itm['Key'][-59:-59+19].split('-')]
                dt = datetime(pts[0], pts[1], pts[2], pts[3], pts[4], pts[5]).replace(tzinfo=pytz.utc)
                if dt < not_before:
                    to_delete.append({
                        'Key': itm['Key']
                    })
                    if len(to_delete) > 999:
                        self._delete_files(client, bucket_name, to_delete)
                        to_delete = []
                else:
                    files_to_handle.append(itm['Key'])

        self._delete_files(client, bucket_name, to_delete)
        return self._process_files(client, bucket_name, files_to_handle)

    def _get_messages_from_cloudtrail(self, not_before):
        client = self.session.client("cloudtrail")
        # collect the events (ordering is most recent event first)
        for pg in client.get_paginator("lookup_events").paginate(
            LookupAttributes=[{"AttributeKey": "ReadOnly", "AttributeValue": "false"}],
        ):
            for itm in pg.get("Events") or []:
                rec = json.loads(itm["CloudTrailEvent"])
                event_date = dateutil.parser.isoparse(rec["eventTime"])
                if event_date > not_before:
                    yield rec

    def _delete_files(self, client, bucket_name, files):
        if len(files) > 0:
            client.delete_objects(
                Bucket=bucket_name,
                Delete={
                    'Objects': files,
                    'Quiet': True
                },
            )

    def _process_files(self, client, bucket_name, files):
        for file in reversed(files):
            objects = []
            with gzip.GzipFile(fileobj=io.BytesIO(client.get_object(Bucket=bucket_name, Key=file)['Body'].read()), mode='rb') as data:
                decoder = json.JSONDecoder()
                txt = data.read().decode('ascii')
                while txt:
                    obj, index = decoder.raw_decode(txt)
                    txt = txt[index:]
                    objects.append(obj["detail"])
                for event in reversed(objects):
                    yield event
        self._delete_files(client, bucket_name, files)
