from ..utils import make_valid_data, with_dimensions
from .registry import RegisteredResource


class firehose(RegisteredResource):
    API = "firehose"
    COMPONENT_TYPE = "aws.firehose"

    def process_all(self):
        for delivery_stream_name in self.client.list_delivery_streams(Limit=10000).get("DeliveryStreamNames") or []:
            delivery_stream_raw = self.client.describe_delivery_stream(DeliveryStreamName=delivery_stream_name)
            delivery_stream = make_valid_data(delivery_stream_raw)
            self.process_delivery_stream(delivery_stream_name, delivery_stream)

    def process_delivery_stream(self, delivery_stream_name, delivery_stream):
        delivery_stream_description = delivery_stream["DeliveryStreamDescription"]
        delivery_stream["Tags"] = (
            self.client.list_tags_for_delivery_stream(DeliveryStreamName=delivery_stream_name).get("Tags") or []
        )
        delivery_stream_arn = delivery_stream_description["DeliveryStreamARN"]
        delivery_stream.update(
            with_dimensions([{
                "key": "DeliveryStreamName",
                "value": delivery_stream_description["DeliveryStreamName"]
            }])
        )
        self.agent.component(delivery_stream_arn, self.COMPONENT_TYPE, delivery_stream)
        delivery_stream_type = delivery_stream_description["DeliveryStreamType"]

        if delivery_stream_type == "KinesisStreamAsSource":
            kinesis_stream_source = delivery_stream_description["Source"]["KinesisStreamSourceDescription"]
            kinesis_stream_arn = kinesis_stream_source["KinesisStreamARN"]
            self.agent.relation(kinesis_stream_arn, delivery_stream_arn, "uses service", {})

        for destination in delivery_stream_description["Destinations"]:
            s3_destination_description = destination.get("S3DestinationDescription")
            if s3_destination_description:
                bucket_arn = s3_destination_description["BucketARN"]
                self.agent.relation(delivery_stream_arn, bucket_arn, "uses service", {})
