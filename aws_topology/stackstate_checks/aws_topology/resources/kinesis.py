from .utils import make_valid_data, create_arn as arn
from .registry import RegisteredResourceCollector


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='kinesis', region=region, account_id=account_id, resource_id='stream/' + resource_id)


class KinesisCollector(RegisteredResourceCollector):
    API = "kinesis"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.kinesis"
    MEMORY_KEY = "kinesis_stream"

    def process_all(self):
        kinesis_stream = {}
        for list_streams_page in self.client.get_paginator('list_streams').paginate():
            for stream_name in list_streams_page.get('StreamNames') or []:
                result = self.process_stream(stream_name)
                kinesis_stream.update(result)
        return kinesis_stream

    def process_stream(self, stream_name):
        stream_summary_raw = self.client.describe_stream_summary(StreamName=stream_name)
        stream_summary = make_valid_data(stream_summary_raw)
        stream_tags = self.client.list_tags_for_stream(StreamName=stream_name).get('Tags') or []
        stream_summary['Tags'] = stream_tags
        stream_arn = stream_summary['StreamDescriptionSummary']['StreamARN']
        self.agent.component(stream_arn, self.COMPONENT_TYPE, stream_summary)
        return {stream_name: stream_arn}
