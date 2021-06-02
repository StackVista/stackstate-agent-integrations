from .utils import make_valid_data, create_arn as arn
from .registry import RegisteredResourceCollector


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='kinesis', region=region, account_id=account_id, resource_id='stream/' + resource_id)


class KinesisCollector(RegisteredResourceCollector):
    API = "kinesis"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.kinesis"
    CLOUDFORMATION_TYPE = 'AWS::Kinesis::Stream'

    def process_all(self, filter=None):
        for list_streams_page in self.client.get_paginator('list_streams').paginate():
            for stream_name in list_streams_page.get('StreamNames') or []:
                self.process_stream(stream_name)

    def process_stream(self, stream_name):
        stream_summary_raw = self.client.describe_stream_summary(StreamName=stream_name)
        stream_summary = make_valid_data(stream_summary_raw)
        stream_tags = self.client.list_tags_for_stream(StreamName=stream_name).get('Tags') or []
        stream_summary['Name'] = stream_name
        stream_summary['Tags'] = stream_tags
        stream_arn = stream_summary['StreamDescriptionSummary']['StreamARN']
        self.emit_component(stream_arn, self.COMPONENT_TYPE, stream_summary)
        # There can also be relations with EC2 instances as enhanced fan out consumers

    EVENT_SOURCE = "kinesis.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {
            'event_name': 'CreateStream',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'DeleteStream',
            'path': 'requestParameters.streamName',
            'processor': RegisteredResourceCollector.process_delete_by_name
        },
        {
            'event_name': 'AddTagsToStream',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'RemoveTagsFromStream',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'StartStreamEncryption',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'StopStreamEncryption',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'UpdateShardCount',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'DisableEnhancedMonitoring',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'EnableEnhancedMonitoring',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'IncreaseStreamRetentionPeriod',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        },
        {
            'event_name': 'DecreaseStreamRetentionPeriod',
            'path': 'requestParameters.streamName',
            'processor': process_stream
        }
        # TODO events
        # RegisterStreamConsumer ???
        # DeregisterStreamConsumer ???
        # MergeShards
        # SplitShard
    ]
