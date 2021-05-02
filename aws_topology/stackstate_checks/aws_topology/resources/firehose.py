from .utils import make_valid_data, with_dimensions, create_arn as arn, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='firehose', region=region, account_id=account_id, resource_id='deliverystream/' + resource_id)


class Firehose_CreateStream(CloudTrailEventBase):
    class ResponseElements(Model):
        deliveryStreamARN = StringType(required=True)

    responseElements = ModelType(ResponseElements, required=True)

    def _internal_process(self, event_name, session, location, agent):
        client = session.client('firehose')
        collector = FirehoseCollector(location, client, agent)
        # TODO make splitting safer
        part = self.responseElements.deliveryStreamARN.split(':')[-1:].pop()
        name = part.split('/')[-1:].pop()
        collector.process_delivery_stream(name)


class Firehose_UpdateStream(CloudTrailEventBase):
    class RequestParameters(Model):
        deliveryStreamName = StringType(required=True)

    requestParameters = ModelType(RequestParameters)

    def _internal_process(self, event_name, session, location, agent):
        if event_name == 'DeleteDeliveryStream':
            agent.delete(agent.create_arn(
                'AWS::KinesisFirehose::DeliveryStream',
                self.requestParameters.deliveryStreamName
            ))
        else:
            client = session.client('firehose')
            collector = FirehoseCollector(location, client, agent)
            collector.process_delivery_stream(self.requestParameters.deliveryStreamName)


class FirehoseCollector(RegisteredResourceCollector):
    API = "firehose"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.firehose"
    EVENT_SOURCE = 'firehose.amazonaws.com'
    CLOUDTRAIL_EVENTS = {
        'CreateDeliveryStream': Firehose_CreateStream,
        'DeleteDeliveryStream': Firehose_UpdateStream,
        'UpdateDestination': Firehose_UpdateStream,
        'TagDeliveryStream': Firehose_UpdateStream,
        'UntagDeliveryStream': Firehose_UpdateStream,
        'StartDeliveryStreamEncryption': Firehose_UpdateStream,
        'StopDeliveryStreamEncryption': Firehose_UpdateStream,
    }

    def process_all(self, filter=None):
        for delivery_stream_name in self.client.list_delivery_streams(Limit=10000).get("DeliveryStreamNames") or []:
            self.process_delivery_stream(delivery_stream_name)

    def process_delivery_stream(self, delivery_stream_name):
        delivery_stream_raw = self.client.describe_delivery_stream(DeliveryStreamName=delivery_stream_name)
        delivery_stream = make_valid_data(delivery_stream_raw)
        delivery_stream_description = delivery_stream.get("DeliveryStreamDescription")
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

        # There can also be a relation with a lambda that is uses to transform the data
        # There can also be a relation with a AWS Glue (region / database / table / version) cross region!
        # There can also be a relation with another S3 bucket for source record backup

        # Destinations can also be S3 / Redshift / ElasticSearch / HTTP / Third Party Service Provider
