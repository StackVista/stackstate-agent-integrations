import time
from ..utils import make_valid_data, correct_tags


def process_kinesis_streams(location_info, client, agent):
    kinesis_stream = {}
    for list_streams_page in client.get_paginator('list_streams').paginate():
        for stream_name_raw in list_streams_page.get('StreamNames') or []:
            stream_name = make_valid_data(stream_name_raw)
            stream_summary = client.describe_stream_summary(StreamName=stream_name)
            stream_tags = client.list_tags_for_stream(StreamName=stream_name)['Tags']
            stream_summary['Tags'] = stream_tags
            stream_arn = stream_summary['StreamDescriptionSummary']['StreamARN']
            stream_summary.update(location_info)
            agent.component(stream_arn, 'aws.kinesis', correct_tags(stream_summary))
            kinesis_stream[stream_name] = stream_arn
            time.sleep(2)
