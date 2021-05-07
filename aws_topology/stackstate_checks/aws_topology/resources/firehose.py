from .utils import make_valid_data, with_dimensions, create_arn as arn, CloudTrailEventBase, client_array_operation, set_required_access_v2, transformation
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ModelType, ListType


class RELATION_TYPE:
      USES_SERVICE = "uses service"

def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='firehose', region=region, account_id=account_id, resource_id='deliverystream/' + resource_id)


class Firehose_CreateStream(CloudTrailEventBase):
    class ResponseElements(Model):
        deliveryStreamARN = StringType(required=True)

    responseElements = ModelType(ResponseElements, required=True)

    def _internal_process(self, event_name, session, location, agent):
        client = session.client('firehose')
        collector = FirehoseCollector(location, client, agent)
        part = self.responseElements.deliveryStreamARN.rsplit(':', 1)[-1]
        name = part.rsplit('/', 1)[-1]
        collector.process_one_delivery_stream(name)


class Firehose_UpdateStream(CloudTrailEventBase):
    class RequestParameters(Model):
        deliveryStreamName = StringType(required=True)

    requestParameters = ModelType(RequestParameters)

    def _internal_process(self, event_name, session, location, agent):
        if event_name == 'DeleteDeliveryStream':
            agent.delete(agent.create_arn(
                FirehoseCollector.CLOUDFORMATION_TYPE,
                self.requestParameters.deliveryStreamName
            ))
        else:
            client = session.client('firehose')
            collector = FirehoseCollector(location, client, agent)
            collector.process_one_delivery_stream(self.requestParameters.deliveryStreamName)


DeliveryStreamData = namedtuple('DeliveryStreamData', ['stream', 'tags'])

class KinesisStreamSourceDescription(Model):
    KinesisStreamARN = StringType()

class DeliveryStreamSource(Model):
    KinesisStreamSourceDescription = ModelType(KinesisStreamSourceDescription)

class DeliveryStreamS3Destination(Model):
    BucketARN = StringType(required=True)

class DeliveryStreamDestinations(Model):
    S3DestinationDescription = ModelType(DeliveryStreamS3Destination, default=[])

class DeliveryStreamDescription(Model):
    DeliveryStreamARN = StringType(required=True)
    DeliveryStreamType = StringType(required=True)
    DeliveryStreamName = StringType(required=True)
    Source = ModelType(DeliveryStreamSource)
    Destinations = ListType(ModelType(DeliveryStreamDestinations, default=[]))

class DeliveryStream(Model):
    DeliveryStreamDescription = ModelType(DeliveryStreamDescription , required=True)

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
    CLOUDFORMATION_TYPE = 'AWS::KinesisFirehose::DeliveryStream'

    @set_required_access_v2('firehose:ListTagsForDeliveryStream')
    def collect_tags(self, stream_name):
        try:
            return self.client.list_tags_for_delivery_stream(DeliveryStreamName=stream_name).get("Tags") or []
        except Exception:
            return []

    @set_required_access_v2('firehose:DescribeDeliveryStream')
    def collect_stream_description(self, stream_name):
        try:
            return self.client.describe_delivery_stream(DeliveryStreamName=stream_name)
        except Exception:
            return {}

    def collect_stream(self, stream_name):
        tags = self.collect_tags(stream_name)
        data = self.collect_stream_description(stream_name)
        return DeliveryStreamData(stream=data, tags=tags)

    def collect_streams(self):
        for stream in [
                self.collect_stream(stream_name) for stream_name in client_array_operation(
                    self.client,
                    'list_delivery_streams',
                    'DeliveryStreamNames'
                )
        ]:
            yield stream

    @set_required_access_v2('firehose:ListDeliveryStreams')
    def process_all(self, filter=None):
        if not filter or 'streams' in filter:
            for stream_data in self.collect_streams():
                try:
                    self.process_delivery_stream(stream_data)
                except Exception:
                    pass

    def process_one_delivery_stream(self, stream_name):
        self.process_delivery_stream(self.collect_stream(stream_name))

    @transformation()
    def process_delivery_stream(self, data):
        output = make_valid_data(data.stream)
        stream = DeliveryStream(data.stream, strict=False)
        stream.validate()
        output["Tags"] = data.tags
        description = stream.DeliveryStreamDescription
        delivery_stream_arn = description.DeliveryStreamARN
        output.update(
            with_dimensions([{
                "key": "DeliveryStreamName",
                "value": description.DeliveryStreamName
            }])
        )
        self.agent.component(delivery_stream_arn, self.COMPONENT_TYPE, output)

        if description.DeliveryStreamType == "KinesisStreamAsSource":
            source = description.Source
            if source:
                kinesis_stream_arn = source.KinesisStreamSourceDescription.KinesisStreamARN
                self.agent.relation(kinesis_stream_arn, delivery_stream_arn, RELATION_TYPE.USES_SERVICE, {})

        for destination in description.Destinations:
            if destination.S3DestinationDescription:
                self.agent.relation(
                    delivery_stream_arn,
                    destination.S3DestinationDescription.BucketARN,
                    "uses service",
                    {}
                )

        # There can also be a relation with a lambda that is uses to transform the data
        # There can also be a relation with a AWS Glue (region / database / table / version) cross region!
        # There can also be a relation with another S3 bucket for source record backup

        # Destinations can also be S3 / Redshift / ElasticSearch / HTTP / Third Party Service Provider
