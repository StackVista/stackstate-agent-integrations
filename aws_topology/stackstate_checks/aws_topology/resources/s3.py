from ..utils import make_valid_data, correct_tags


def process_s3(location_info, client, agent):
    s3_bucket = {}
    for bucket_data_raw in client.list_buckets().get('Buckets') or []:
        bucket_data = make_valid_data(bucket_data_raw)
        bucket_name = bucket_data['Name']
        bucket_arn = 'arn:aws:s3:::' + bucket_name
        bucket_location = client.get_bucket_location(Bucket=bucket_name)
        if bucket_location and bucket_location['LocationConstraint']:
            bucket_data['BucketLocation'] = bucket_location['LocationConstraint']
        try:
            # raises error when there aren't any tags, see:https://github.com/boto/boto3/issues/341
            bucket_tags = client.get_bucket_tagging(Bucket=bucket_name)['TagSet']
        except Exception:
            bucket_tags = []
        bucket_data['Tags'] = bucket_tags
        bucket_data.update(location_info)
        agent.component(bucket_arn, 'aws.s3_bucket', correct_tags(bucket_data))
        s3_bucket[bucket_name] = bucket_arn
        bucket_notification_configurations = client.get_bucket_notification_configuration(
            Bucket=bucket_name).get(
            'LambdaFunctionConfigurations')
        if bucket_notification_configurations:
            for bucket_notification in bucket_notification_configurations:
                function_arn = bucket_notification['LambdaFunctionArn']
                for event_raw in bucket_notification['Events']:
                    event = make_valid_data(event_raw)
                    agent.relation(bucket_arn, function_arn, 'uses service', {"event_type": event})
    return s3_bucket
