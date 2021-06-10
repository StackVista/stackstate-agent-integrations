from .utils import make_valid_data, create_arn as arn, client_array_operation
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ListType


def create_arn(resource_id=None, **kwargs):
    return arn(resource="s3", region="", account_id="", resource_id=resource_id)


BucketData = namedtuple("BucketData", ["bucket", "location", "tags", "config"])


class Bucket(Model):
    Name = StringType()


class BucketNotification(Model):
    LambdaFunctionArn = StringType(required=True)
    Events = ListType(StringType, required=True)


class S3Collector(RegisteredResourceCollector):
    API = "s3"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.s3_bucket"
    CLOUDFORMATION_TYPE = "AWS::S3::Bucket"

    def collect_location(self, name):
        return self.client.get_bucket_location(Bucket=name).get("LocationConstraint", "")

    def collect_tags(self, name):
        return self.client.get_bucket_tagging(Bucket=name).get("TagSet", [])

    def collect_configuration(self, name):
        return self.client.get_bucket_notification_configuration(Bucket=name).get("LambdaFunctionConfigurations", [])

    def collect_bucket(self, bucket):
        name = bucket.get("Name")
        location = self.collect_location(name) or ""
        tags = self.collect_tags(name) or []
        config = self.collect_configuration(name) or []
        return BucketData(bucket=bucket, location=location, tags=tags, config=config)

    def collect_buckets(self):
        for bucket in [
            self.collect_bucket(bucket) for bucket in client_array_operation(self.client, "list_buckets", "Buckets")
        ]:
            yield bucket

    def process_all(self, filter=None):
        # TODO buckets should only be fetched for global OR filtered by LocationConstraint
        if not filter or "buckets" in filter:
            for bucket_data in self.collect_buckets():
                self.process_bucket(bucket_data)

    def process_one_bucket(self, bucket_name):
        self.process_bucket(self.collect_bucket({"Name": bucket_name}))

    def process_bucket(self, data):
        output = make_valid_data(data.bucket)

        bucket = Bucket(data.bucket, strict=False)
        config = [BucketNotification(notification, strict=False) for notification in data.config]

        bucket_name = bucket.Name
        bucket_arn = create_arn(resource_id=bucket_name)

        if data.location:
            output["BucketLocation"] = data.location
        output["Tags"] = data.tags

        self.emit_component(bucket_arn, self.COMPONENT_TYPE, output)
        for bucket_notification in config:
            function_arn = bucket_notification.LambdaFunctionArn
            if function_arn:  # pragma: no cover
                for event in bucket_notification.Events:
                    self.emit_relation(bucket_arn, function_arn, "uses service", {"event_type": event})

    EVENT_SOURCE = "s3.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateBucket", "path": "requestParameters.bucketName", "processor": process_one_bucket},
        {
            "event_name": "DeleteBucket",
            "path": "requestParameters.bucketName",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
    ]
