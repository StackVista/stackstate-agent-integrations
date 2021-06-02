from .utils import (
    make_valid_data,
    with_dimensions,
    create_arn as arn,
    CloudTrailEventBase,
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


class DynamoDBEventBase(CloudTrailEventBase):
    def get_collector_class(self):
        return DynamodbTableCollector

    def _internal_process(self, session, location, agent):
        if self.get_operation_type() == "D":
            agent.delete(self.get_resource_arn(agent, location))
        else:
            client = session.client("dynamodb")
            collector = DynamodbTableCollector(location, client, agent)
            collector.process_one_table(self.get_resource_name())


class DynamoDB_UpdateTable(DynamoDBEventBase):
    class RequestParameters(Model):
        tableName = StringType(required=True)

    requestParameters = ModelType(RequestParameters, required=True)

    def get_resource_name(self):
        return self.requestParameters.tableName

    def get_operation_type(self):
        return "D" if self.eventName == "DeleteTable" else "U"


class DynamoDB_TagResource(DynamoDBEventBase):
    class RequestParameters(Model):
        resourceArn = StringType(required=True)

    requestParameters = ModelType(RequestParameters)

    def get_operation_type(self):
        return "U"

    def get_resource_name(self):
        return self.requestParameters.resourceArn.split(":")[-1]


class TableStreamSpecification(Model):
    StreamEnabled = BooleanType()
    StreamViewType = StringType()


class TableDescription(Model):
    TableArn = StringType()
    TableName = StringType(required=True)
    StreamSpecification = ModelType(TableStreamSpecification)
    LatestStreamLabel = StringType()
    LatestStreamArn = StringType()


class Table(Model):
    Table = ModelType(TableDescription, required=True)


class DynamodbTableCollector(RegisteredResourceCollector):
    API = "dynamodb"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.dynamodb"
    EVENT_SOURCE = "dynamodb.amazonaws.com"
    CLOUDTRAIL_EVENTS = {
        "CreateTable": DynamoDB_UpdateTable,
        "DeleteTable": DynamoDB_UpdateTable,
        "TagResource": DynamoDB_TagResource,
        "UntagResource": DynamoDB_TagResource
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
    }
    CLOUDFORMATION_TYPE = "AWS::DynamoDB::Table"

    @set_required_access_v2("dynamodb:ListTagsOfResource")
    def collect_tags(self, table_arn):
        return self.client.list_tags_of_resource(ResourceArn=table_arn).get("Tags", [])

    @set_required_access_v2("dynamodb:DescribeTable")
    def collect_table_description(self, table_name):
        return self.client.describe_table(TableName=table_name)

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
        description = table.Table
        output = make_valid_data(description.to_primitive())
        table_arn = description.TableArn
        table_name = description.TableName
        output["Name"] = table_arn
        output["Tags"] = data.tags
        output.update(with_dimensions([{"key": "TableName", "value": table_name}]))
        self.emit_component(table_arn, self.COMPONENT_TYPE, output)

        latest_stream_arn = description.LatestStreamArn
        stream_specification = description.StreamSpecification.to_primitive()
        # TODO also streaming to kinesis also possible (relation)
        # TODO global tables possible (regions specified)
        # TODO has default alarms
        if latest_stream_arn and stream_specification:
            latest_stream_label = description.LatestStreamLabel
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
