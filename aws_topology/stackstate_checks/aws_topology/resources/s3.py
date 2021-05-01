from .utils import make_valid_data, create_arn as arn, client_array_operation, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ListType, ModelType


def create_arn(resource_id=None, **kwargs):
    return arn(resource='s3', region='', account_id='', resource_id=resource_id)


BucketData = namedtuple('BucketData', ['bucket', 'location', 'tags', 'config'])


class Bucket(Model):
    Name = StringType()


class BucketNotification(Model):
    LambdaFunctionArn = StringType(required=True)
    Events = ListType(StringType, required=True)


class S3_UpdateBucket(CloudTrailEventBase):
    class RequestParameters(Model):
        bucketName = StringType(required=True)

    requestParameters = ModelType(RequestParameters, required=True)

    def _internal_process(self, event_name, session, location, agent):
        if event_name == 'DeleteBucket':
            agent.delete(agent.create_arn(
                'AWS::S3::Bucket',
                self.requestParameters.bucketName
            ))
        else:
            client = session.client('s3')
            collector = S3Collector(location, client, agent)
            collector.process_one_bucket(self.requestParameters.bucketName)


class S3Collector(RegisteredResourceCollector):
    API = "s3"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.s3_bucket"
    EVENT_SOURCE = 's3.amazonaws.com'
    CLOUDTRAIL_EVENTS = {
        'CreateBucket': S3_UpdateBucket,
        'DeleteBucket': S3_UpdateBucket
    }

    def collect_bucket(self, bucket):
        name = bucket.get('Name')
        try:
            location = self.client.get_bucket_location(Bucket=name).get('LocationConstraint', '')
        except Exception:  # TODO catch throttle + permission exceptions
            location = ''
        try:
            tags = self.client.get_bucket_tagging(Bucket=name).get("TagSet", [])
        except Exception:  # TODO catch throttle + permission exceptions
            tags = []
        try:
            config = self.client.get_bucket_notification_configuration(Bucket=name).get(
                "LambdaFunctionConfigurations", []
            )
        except Exception:  # TODO catch throttle + permission exceptions
            config = []
        return BucketData(bucket=bucket, location=location, tags=tags, config=config)

    def collect_buckets(self):
        for bucket in [
                self.collect_bucket(bucket) for bucket in client_array_operation(
                    self.client,
                    'list_buckets',
                    'Buckets'
                )
        ]:
            yield bucket

    def process_all(self):
        s3_buckets = {}
        # buckets should only be fetched for global OR filtered by LocationConstraint
        for bucket_data in self.collect_buckets():
            s3_buckets.update(self.process_bucket(bucket_data))
        return s3_buckets

    def process_one_bucket(self, bucket_name):
        self.process_bucket(self.collect_bucket({'Name': bucket_name}))

    def process_bucket(self, data):
        output = make_valid_data(data.bucket)

        bucket = Bucket(data.bucket, strict=False)
        config = [BucketNotification(notification, strict=False) for notification in data.config]

        bucket_name = bucket.Name
        bucket_arn = create_arn(resource_id=bucket_name)

        if data.location:
            output["BucketLocation"] = data.location
        output["Tags"] = data.tags

        self.agent.component(bucket_arn, self.COMPONENT_TYPE, output)
        for bucket_notification in config:
            function_arn = bucket_notification.LambdaFunctionArn
            if function_arn:
                for event in bucket_notification.Events:
                    self.agent.relation(bucket_arn, function_arn, "uses service", {"event_type": event})
        return {bucket_name: bucket_arn}
