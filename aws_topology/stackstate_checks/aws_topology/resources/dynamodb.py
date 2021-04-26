from .utils import make_valid_data, with_dimensions, create_arn as arn
from .registry import RegisteredResourceCollector


def create_table_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='dynamodb', region=region, account_id=account_id, resource_id='table/' + resource_id)


class DynamodbTableCollector(RegisteredResourceCollector):
    API = "dynamodb"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.dynamodb"

    def process_all(self):
        dynamodb = {}
        for page in self.client.get_paginator('list_tables').paginate():
            for table_name in page.get('TableNames') or []:
                result = self.process_table(table_name)
                dynamodb.update(result)
        return dynamodb

    def process_table(self, table_name):
        table_description_raw = self.client.describe_table(TableName=table_name)
        table_description = make_valid_data(table_description_raw)
        table_data = table_description['Table']
        table_arn = table_data['TableArn']
        table_tags = self.client.list_tags_of_resource(ResourceArn=table_arn).get('Tags') or []
        table_data['Tags'] = table_tags
        table_data['Name'] = table_arn
        table_data.update(with_dimensions([{'key': 'TableName', 'value': table_name}]))
        self.agent.component(table_arn, self.COMPONENT_TYPE, table_data)
        latest_stream_arn = table_data.get('LatestStreamArn')
        if latest_stream_arn and table_data.get('StreamSpecification'):
            stream_specification = table_data['StreamSpecification']
            latest_stream_label = table_data['LatestStreamLabel']
            stream_specification['LatestStreamArn'] = latest_stream_arn
            stream_specification['LatestStreamLabel'] = latest_stream_label
            stream_specification['Name'] = latest_stream_arn
            stream_specification.update(with_dimensions([
                {'key': 'TableName', 'value': table_name},
                {'key': 'StreamLabel', 'value': latest_stream_label}
            ]))
            self.agent.component(latest_stream_arn, 'aws.dynamodb.streams', stream_specification)
            self.agent.relation(table_arn, latest_stream_arn, 'uses service', {})
        return {table_name: table_arn}
