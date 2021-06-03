from .utils import (
    make_valid_data,
    with_dimensions,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, BooleanType, ModelType

"""DynamodbTableCollector

Tables
    list_tables
        list_tags_of_resource
        describe_table
"""


def create_table_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="dynamodb", region=region, account_id=account_id, resource_id="table/" + resource_id)


TableData = namedtuple("TableData", ["table", "tags"])


class TableStreamSpecification(Model):
    StreamEnabled = BooleanType()
    StreamViewType = StringType()


class Table(Model):
    TableArn = StringType()
    TableName = StringType(required=True)
    StreamSpecification = ModelType(TableStreamSpecification)
    LatestStreamLabel = StringType()
    LatestStreamArn = StringType()


class DynamodbTableCollector(RegisteredResourceCollector):
    API = "dynamodb"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.dynamodb"
    CLOUDFORMATION_TYPE = "AWS::DynamoDB::Table"

    @set_required_access_v2("dynamodb:ListTagsOfResource")
    def collect_tags(self, table_arn):
        return self.client.list_tags_of_resource(ResourceArn=table_arn).get("Tags", [])

    @set_required_access_v2("dynamodb:DescribeTable")
    def collect_table_description(self, table_name):
        return self.client.describe_table(TableName=table_name).get("Table", {})

    def construct_table_description(self, table_name):
        return {
            "Table": {
                "TableName": table_name,
                "TableArn": self.agent.create_arn("AWS::DynamoDB::Table", self.location_info, resource_id=table_name),
            }
        }

    def collect_table(self, table_name):
        # If data collection fails, construct the ARN
        data = self.collect_table_description(table_name) or self.construct_table_description(table_name)
        # If ARN creation fails, skip tag collection
        if data.get("Table", {}).get("TableArn"):
            tags = self.collect_tags(data["Table"]["TableArn"])
        else:
            tags = []
        return TableData(table=data, tags=tags)

    @set_required_access_v2("dynamodb:ListTables")
    def collect_tables(self):
        for table in [
            self.collect_table(table_name)
            for table_name in client_array_operation(self.client, "list_tables", "TableNames")
        ]:
            yield table

    def process_all(self, filter=None):
        if not filter or "dynamodb" in filter:
            for table_data in self.collect_tables():
                try:
                    self.process_table(table_data)
                except Exception:
                    pass

    def process_one_table(self, table_name):
        self.process_table(self.collect_table(table_name))

    @transformation()
    def process_table(self, data):
        table = Table(data.table, strict=False)
        table.validate()
        output = make_valid_data(data.table)
        table_arn = table.TableArn
        table_name = table.TableName
        output["Name"] = table_arn
        output["Tags"] = data.tags
        output.update(with_dimensions([{"key": "TableName", "value": table_name}]))
        self.emit_component(table_arn, self.COMPONENT_TYPE, output)

        latest_stream_arn = table.LatestStreamArn
        stream_specification = table.StreamSpecification
        # TODO also streaming to kinesis also possible (relation)
        # TODO global tables possible (regions specified)
        # TODO has default alarms
        if latest_stream_arn and stream_specification:
            stream = make_valid_data(data.table.get("StreamSpecification", {}))
            latest_stream_label = table.LatestStreamLabel
            stream["LatestStreamArn"] = latest_stream_arn
            stream["LatestStreamLabel"] = latest_stream_label
            stream["Name"] = latest_stream_arn
            stream.update(
                with_dimensions(
                    [{"key": "TableName", "value": table_name}, {"key": "StreamLabel", "value": latest_stream_label}]
                )
            )
            self.emit_component(latest_stream_arn, "aws.dynamodb.streams", stream)
            self.emit_relation(table_arn, latest_stream_arn, "uses service", {})
        return {table_name: table_arn}

    def process_resource(self, arn):
        name = arn.split(":")[-1]
        self.process_one_table(name)

    EVENT_SOURCE = "dynamodb.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateTable", "path": "requestParameters.tableName", "processor": process_one_table},
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
