from .utils import (
    make_valid_data,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ModelType


def create_arn(resource_id, region, account_id, **kwargs):
    return arn(resource="lambda", region=region, account_id=account_id, resource_id="function:" + resource_id)


FunctionData = namedtuple("FunctionData", ["function", "tags", "aliases"])


class EventSource(Model):
    FunctionArn = StringType(required=True)
    EventSourceArn = StringType(required=True)
    State = StringType(default="Enabled")


class FunctionAlias(Model):
    AliasArn = StringType(required=True)


class Function(Model):
    class FunctionVpcConfig(Model):
        VpcId = StringType(required=True)

    FunctionName = StringType(required=True)
    FunctionArn = StringType(required=True)
    VpcConfig = ModelType(FunctionVpcConfig)


class LambdaCollector(RegisteredResourceCollector):
    API = "lambda"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.lambda"

    @set_required_access_v2("lambda:ListTags")
    def collect_tags(self, function_arn):
        return self.client.list_tags(Resource=function_arn).get("Tags", [])

    @set_required_access_v2("lambda:ListAliases")
    def collect_aliases(self, function_name):
        return [
            aliases
            for aliases in client_array_operation(self.client, "list_aliases", "Aliases", FunctionName=function_name)
        ]

    def collect_function(self, function_data):
        function_name = function_data.get("FunctionName", "")
        tags = self.collect_tags(function_name) or []
        aliases = self.collect_aliases(function_name) or []
        return FunctionData(data=function_data, tags=tags, aliases=aliases)

    def collect_functions(self, **kwargs):
        for function in [
            self.collect_function(function_data)
            for function_data in client_array_operation(self.client, "list_functions", "Functions", **kwargs)
        ]:
            yield function

    def collect_event_sources(self):
        for event_source in client_array_operation(self, "list_event_source_mappings", "EventSourceMappings"):
            yield event_source

    @set_required_access_v2("lambda:ListFunctions")
    def process_functions(self):
        for function_data in self.collect_functions():
            self.process_function(function_data)

    @set_required_access_v2("lambda:ListEventSourceMappings")
    def process_event_sources(self):
        for event_source_data in self.collect_event_sources():
            self.process_event_source(event_source_data)

    def process_all(self, filter=None):
        if not filter or "functions" in filter:
            self.process_functions()
        if not filter or "mappings" in filter:
            self.process_event_sources()

    def process_one_function(self, function_name):
        for function_data in self.collect_functions(FunctionName=function_name):
            self.process_function(function_data)

    @transformation()
    def process_event_source(self, data):
        event_source = EventSource(data, strict=False)
        event_source.validate()
        if event_source.State == "Enabled":
            output = make_valid_data(data)
            # Swapping source/target: StackState models dependencies, not data flow
            self.emit_relation(event_source.FunctionArn, event_source.EventSourceArn, "uses service", output)

    @transformation()
    def process_function(self, data):
        function = Function(data.function, strict=False)
        function.validate()
        output = make_valid_data(data.function)
        function_arn = function.FunctionArn
        output["Name"] = function.FunctionName
        output["Tags"] = data.tags
        self.emit_component(function_arn, self.COMPONENT_TYPE, output)

        if function.VpcConfig.VpcId:
            self.emit_relation(function_arn, function.VpcConfig.VpcId, "uses service", {})
            self.agent.create_security_group_relations(function_arn, output.get("VpcConfig"), "SecurityGroupIds")
        # TODO also emit versions as components and relation to alias / canaries
        # https://stackstate.atlassian.net/browse/STAC-13113
        for alias_data in data.aliases:
            alias = FunctionAlias(alias_data, strict=False)
            alias.validate()
            alias_output = make_valid_data(alias_data)
            alias_output["Function"] = output
            self.emit_component(alias.AliasArn, "aws.lambda.alias", alias_output)
            if function.VpcConfig.VpcId:
                self.emit_relation(alias.AliasArn, function.VpcConfig.VpcId, "uses service", {})

    CLOUDFORMATION_TYPE = "AWS::Lambda::Function"
    EVENT_SOURCE = "lambda.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {
            "event_name": "CreateFunction20150331",
            "path": "responseElements.functionArn",
            "processor": process_one_function,
        },
        {
            "event_name": "UpdateFunctionConfiguration20150331v2",
            "path": "responseElements.functionArn",
            "processor": process_one_function,
        },
        {
            "event_name": "PublishVersion20150331",
            "path": "responseElements.functionName",
            "processor": process_one_function,
        },
        {
            "event_name": "AddPermission20150331v2",
            "path": "requestParameters.functionName",
            "processor": process_one_function,  # TODO check responseElements not null!
        },
        {
            "event_name": "TagResource20170331v2",
            "path": "requestParameters.resource",
            "processor": process_one_function,
        },
        {
            "event_name": "CreateEventSourceMapping20150331",
            "path": "responseElements.functionArn",
            "processor": process_one_function,
        },
        {
            "event_name": "DeleteFunction20150331",
            "path": "requestParameters.functionName",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        }
        # AddLayerVersionPermission
        # RemovePermission
        # CreateEventSourceMapping
        # DeleteEventSourceMapping
        # UpdateEventSourceMapping
        # UpdateFunctionCode
        # UpdateFunctionConfiguration
    ]
