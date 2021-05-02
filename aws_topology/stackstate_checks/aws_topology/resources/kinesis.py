from .utils import make_valid_data, create_arn as arn, CloudTrailEventBase
from schematics import Model
from schematics.types import StringType, ModelType
from .registry import RegisteredResourceCollector


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='kinesis', region=region, account_id=account_id, resource_id='stream/' + resource_id)


class Kinesis_Stream(CloudTrailEventBase):
    class RequestParameters(Model):
        streamName = StringType(required=True)

    requestParameters = ModelType(RequestParameters)

    def _internal_process(self, event_name, session, location, agent):
        if event_name == 'DeleteStream':
            agent.delete(agent.create_arn(
                'AWS::Kinesis::Stream',
                self.requestParameters.streamName
            ))
        else:
            client = session.client('kinesis')
            collector = KinesisCollector(location, client, agent)
            collector.process_stream(self.requestParameters.streamName)


class KinesisCollector(RegisteredResourceCollector):
    API = "kinesis"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.kinesis"
    EVENT_SOURCE = "kinesis.amazonaws.com"
    CLOUDTRAIL_EVENTS = {
        'CreateStream': Kinesis_Stream,  # responseElements sometimes is empty so parsing requestParameters here
        'DeleteStream': Kinesis_Stream,
        'AddTagsToStream': Kinesis_Stream,
        'RemoveTagsFromStream': Kinesis_Stream,
        'StartStreamEncryption': Kinesis_Stream,
        'StopStreamEncryption': Kinesis_Stream,
        'UpdateShardCount': Kinesis_Stream,
        'DisableEnhancedMonitoring': Kinesis_Stream,
        'EnableEnhancedMonitoring': Kinesis_Stream,
        'IncreaseStreamRetentionPeriod': Kinesis_Stream,
        'DecreaseStreamRetentionPeriod': Kinesis_Stream,
        # TODO events
        # RegisterStreamConsumer ???
        # DeregisterStreamConsumer ???
        # MergeShards
        # SplitShard
    }

    def process_all(self, filter=None):
        for list_streams_page in self.client.get_paginator('list_streams').paginate():
            for stream_name in list_streams_page.get('StreamNames') or []:
                self.process_stream(stream_name)

    def process_stream(self, stream_name):
        stream_summary_raw = self.client.describe_stream_summary(StreamName=stream_name)
        stream_summary = make_valid_data(stream_summary_raw)
        stream_tags = self.client.list_tags_for_stream(StreamName=stream_name).get('Tags') or []
        stream_summary['Tags'] = stream_tags
        stream_arn = stream_summary['StreamDescriptionSummary']['StreamARN']
        self.agent.component(stream_arn, self.COMPONENT_TYPE, stream_summary)
        # There can also be relations with EC2 instances as enhanced fan out consumers
