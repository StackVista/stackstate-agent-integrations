from .utils import make_valid_data, with_dimensions, create_arn as arn
from .registry import RegisteredResourceCollector

"""DynamodbTableCollector

Tables
    list_tables
        list_tags_of_resource
        describe_table
"""


def create_table_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="dynamodb", region=region, account_id=account_id, resource_id="table/" + resource_id)


class DynamodbTableCollector(RegisteredResourceCollector):
    API = "dynamodb"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.dynamodb"
    CLOUDFORMATION_TYPE = "AWS::DynamoDB::Table"

    def process_all(self, filter=None):
        for page in self.client.get_paginator("list_tables").paginate():
            for table_name in page.get("TableNames") or []:
                self.process_table(table_name)

    def process_table(self, table_name):
        table_description_raw = self.client.describe_table(TableName=table_name)
        table_description = make_valid_data(table_description_raw)
        table_data = table_description["Table"]
        table_arn = table_data["TableArn"]
        table_tags = self.client.list_tags_of_resource(ResourceArn=table_arn).get("Tags") or []
        table_data["Tags"] = table_tags
        table_data["Name"] = table_arn
        table_data.update(with_dimensions([{"key": "TableName", "value": table_name}]))
        self.emit_component(table_arn, self.COMPONENT_TYPE, table_data)
        latest_stream_arn = table_data.get("LatestStreamArn")
        # TODO also streaming to kinesis also possible (relation)
        # TODO global tables possible (regions specified)
        # TODO has default alarms
        if latest_stream_arn and table_data.get("StreamSpecification"):
            stream_specification = table_data["StreamSpecification"]
            latest_stream_label = table_data["LatestStreamLabel"]
            stream_specification["LatestStreamArn"] = latest_stream_arn
            stream_specification["LatestStreamLabel"] = latest_stream_label
            stream_specification["Name"] = latest_stream_arn
            stream_specification.update(
                with_dimensions(
                    [{"key": "TableName", "value": table_name}, {"key": "StreamLabel", "value": latest_stream_label}]
                )
            )
            self.emit_component(latest_stream_arn, "aws.dynamodb.streams", stream_specification)
            self.emit_relation(table_arn, latest_stream_arn, "uses service", {})
        return {table_name: table_arn}

    def process_resource(self, arn):
        name = arn.split(":")[-1]
        self.process_table(name)

    EVENT_SOURCE = "dynamodb.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateTable", "path": "requestParameters.tableName", "processor": process_table},
        {
            "event_name": "DeleteTable",
            "path": "requestParameters.tableName",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
        {"event_name": "TagResource", "path": "requestParameters.resourceArn", "processor": process_resource},
        {"event_name": "UntagResource", "path": "requestParameters.resourceArn", "processor": process_resource}
        # UpdateTable
        # UpdateTimeToLive
        #
        # Kinesis Stream!
        #
        # UpdateGlobalTable
        # CreateGlobalTable
        # events
        # RestoreTableFromBackup
        # RestoreTableToPointInTime
        # DeleteBackup
    ]
