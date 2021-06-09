from collections import namedtuple
from .utils import (
    make_valid_data,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from schematics import Model
from schematics.types import StringType, ModelType
from .registry import RegisteredResourceCollector


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="kinesis", region=region, account_id=account_id, resource_id="stream/" + resource_id)


StreamData = namedtuple("StreamData", ["stream", "tags"])


class Stream(Model):
    StreamName = StringType(default="UNKNOWN")
    StreamARN = StringType(required=True)


class StreamDescriptionSummary(Model):
    StreamDescriptionSummary = ModelType(Stream)


class KinesisCollector(RegisteredResourceCollector):
    API = "kinesis"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.kinesis"
    CLOUDFORMATION_TYPE = "AWS::Kinesis::Stream"

    @set_required_access_v2("kinesis:ListTagsForStream")
    def collect_tags(self, stream_name):
        return self.client.list_tags_for_stream(StreamName=stream_name).get("Tags", [])

    @set_required_access_v2("kinesis:DescribeStreamSummary")
    def collect_stream_description(self, stream_name):
        return self.client.describe_stream_summary(StreamName=stream_name)

    def construct_stream_description(self, stream_name):
        return {
            "StreamDescriptionSummary": {
                "StreamName": stream_name,
                "StreamARN": self.agent.create_arn("AWS::SNS::Topic", self.location_info, resource_id=stream_name),
            }
        }

    def collect_stream(self, stream_name):
        data = self.collect_stream_description(stream_name) or self.construct_stream_description(stream_name)
        tags = self.collect_tags(stream_name) or []
        return StreamData(stream=data, tags=tags)

    def collect_streams(self):
        for stream in [
            self.collect_stream(stream_name)
            for stream_name in client_array_operation(self.client, "list_streams", "StreamNames")
        ]:
            yield stream

    def process_all(self, filter=None):
        if not filter or "kinesis" in filter:
            self.process_streams()

    @set_required_access_v2("kinesis:ListStreams")
    def process_streams(self):
        for stream_data in self.collect_streams():
            self.process_stream(stream_data)

    def process_one_stream(self, stream_name):
        self.process_stream(self.collect_stream(stream_name))

    @transformation()
    def process_stream(self, data):
        stream = StreamDescriptionSummary(data.stream, strict=False)
        stream.validate()
        output = make_valid_data(data.stream)
        stream_arn = stream.StreamDescriptionSummary.StreamARN
        stream_name = stream.StreamDescriptionSummary.StreamName
        output["Name"] = stream_name
        output["Tags"] = data.tags
        self.emit_component(stream_arn, self.COMPONENT_TYPE, output)
        # There can also be relations with EC2 instances as enhanced fan out consumers

    EVENT_SOURCE = "kinesis.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateStream", "path": "requestParameters.streamName", "processor": process_one_stream},
        {
            "event_name": "DeleteStream",
            "path": "requestParameters.streamName",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
        {"event_name": "AddTagsToStream", "path": "requestParameters.streamName", "processor": process_one_stream},
        {"event_name": "RemoveTagsFromStream", "path": "requestParameters.streamName", "processor": process_one_stream},
        {
            "event_name": "StartStreamEncryption",
            "path": "requestParameters.streamName",
            "processor": process_one_stream,
        },
        {"event_name": "StopStreamEncryption", "path": "requestParameters.streamName", "processor": process_one_stream},
        {"event_name": "UpdateShardCount", "path": "requestParameters.streamName", "processor": process_one_stream},
        {
            "event_name": "DisableEnhancedMonitoring",
            "path": "requestParameters.streamName",
            "processor": process_one_stream,
        },
        {
            "event_name": "EnableEnhancedMonitoring",
            "path": "requestParameters.streamName",
            "processor": process_one_stream,
        },
        {
            "event_name": "IncreaseStreamRetentionPeriod",
            "path": "requestParameters.streamName",
            "processor": process_one_stream,
        },
        {
            "event_name": "DecreaseStreamRetentionPeriod",
            "path": "requestParameters.streamName",
            "processor": process_one_stream,
        }
        # TODO events
        # RegisterStreamConsumer ???
        # DeregisterStreamConsumer ???
        # MergeShards
        # SplitShard
    ]
