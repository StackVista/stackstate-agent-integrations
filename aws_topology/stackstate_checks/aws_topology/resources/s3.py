from .utils import make_valid_data
from .registry import RegisteredResourceCollector


class S3Collector(RegisteredResourceCollector):
    API = "s3"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.s3_bucket"

    def process_all(self):
        s3_bucket = {}
        for bucket_data_raw in self.client.list_buckets().get("Buckets") or []:  # TODO no paginator!
            bucket_data = make_valid_data(bucket_data_raw)
            result = self.process_bucket(bucket_data)
            s3_bucket.update(result)
        return s3_bucket

    def process_bucket(self, bucket_data):
        bucket_name = bucket_data["Name"]
        bucket_arn = "arn:aws:s3:::" + bucket_name  # TODO use proper arn constructor
        bucket_location = self.client.get_bucket_location(Bucket=bucket_name)
        if bucket_location and bucket_location["LocationConstraint"]:
            bucket_data["BucketLocation"] = bucket_location["LocationConstraint"]
        try:
            # raises error when there aren't any tags, see:https://github.com/boto/boto3/issues/341
            bucket_tags = self.client.get_bucket_tagging(Bucket=bucket_name)["TagSet"]
        except Exception:
            bucket_tags = []
        bucket_data["Tags"] = bucket_tags
        self.agent.component(bucket_arn, self.COMPONENT_TYPE, bucket_data)
        bucket_notification_configurations = self.client.get_bucket_notification_configuration(Bucket=bucket_name).get(
            "LambdaFunctionConfigurations"
        )
        if bucket_notification_configurations:
            for bucket_notification in bucket_notification_configurations:
                function_arn = bucket_notification["LambdaFunctionArn"]
                for event_raw in bucket_notification["Events"]:
                    event = make_valid_data(event_raw)
                    self.agent.relation(bucket_arn, function_arn, "uses service", {"event_type": event})
        return {bucket_name: bucket_arn}
