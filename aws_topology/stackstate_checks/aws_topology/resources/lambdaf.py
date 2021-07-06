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
from schematics.types import StringType, ModelType, DictType
import re


def create_arn(resource_id, region, account_id, **kwargs):
    return arn(resource="lambda", region=region, account_id=account_id, resource_id="function:" + resource_id)


FunctionData = namedtuple("FunctionData", ["function", "tags", "aliases"])


class EventSource(Model):
    FunctionArn = StringType(required=True)
    EventSourceArn = StringType(required=True)
    State = StringType(default="UNKNOWN")


class FunctionAlias(Model):
    AliasArn = StringType(required=True)


class Function(Model):
    class EnvironmentVariables(Model):
        Variables = DictType(StringType(), default={})

    class FunctionVpcConfig(Model):
        VpcId = StringType()

    FunctionName = StringType(required=True)
    FunctionArn = StringType(required=True)
    VpcConfig = ModelType(FunctionVpcConfig, default={})
    Environment = ModelType(EnvironmentVariables)


class LambdaCollector(RegisteredResourceCollector):
    API = "lambda"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.lambda"

    # All Lambda API calls can accept the function ARN, Name, or Partial ARN as input
    @set_required_access_v2("lambda:ListTags")
    def collect_tags(self, function_id):
        return self.client.list_tags(Resource=function_id).get("Tags", [])

    @set_required_access_v2("lambda:ListAliases")
    def collect_aliases(self, function_id):
        return [
            aliases
            for aliases in client_array_operation(self.client, "list_aliases", "Aliases", FunctionName=function_id)
        ]

    # list_functions gives the same detail as get_function, but we need this to process one
    @set_required_access_v2("lambda:GetFunction")
    def collect_function_description(self, function_id):
        return self.client.get_function(FunctionName=function_id).get("Configuration", {})

    def collect_function(self, function_data):
        function_arn = function_data.get("FunctionArn", "")
        # Test to see if the function_data has minimal data, or more
        if len(function_data.keys()) <= 2:
            data = self.collect_function_description(function_arn) or function_data
        else:
            data = function_data
        tags = self.collect_tags(function_arn) or []
        aliases = self.collect_aliases(function_arn) or []
        return FunctionData(function=data, tags=tags, aliases=aliases)

    def collect_functions(self):
        for function_data in client_array_operation(self.client, "list_functions", "Functions"):
            yield self.collect_function(function_data)

    def collect_event_sources(self):
        for event_source in client_array_operation(self.client, "list_event_source_mappings", "EventSourceMappings"):
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

    # The inputted value could be either an ARN (with/without version) or a name, we can tell by the number of :
    def process_one_function(self, function_id):
        if len(function_id.split(":")) > 6:
            request = {"FunctionName": function_id.split(":")[6], "FunctionArn": function_id}
        else:
            request = {
                "FunctionName": function_id,
                "FunctionArn": self.agent.create_arn(
                    "AWS::Lambda::Function", self.location_info, resource_id=function_id
                ),
            }
        self.process_function(self.collect_function(request))

    @transformation()
    def process_event_source(self, data):
        event_source = EventSource(data, strict=False)
        event_source.validate()
        if event_source.State == "Enabled":
            output = make_valid_data(data)
            # Swapping source/target: StackState models dependencies, not data flow
            self.emit_relation(event_source.FunctionArn, event_source.EventSourceArn, "uses-service", output)

    @transformation()
    def process_function(self, data):
        function = Function(data.function, strict=False)
        function.validate()
        output = make_valid_data(data.function)
        function_arn = function.FunctionArn
        output["Name"] = function.FunctionName
        output["Tags"] = data.tags
        self.emit_component(function_arn, ".".join([self.COMPONENT_TYPE, "function"]), output)

        if function.VpcConfig.VpcId:
            self.emit_relation(function_arn, function.VpcConfig.VpcId, "uses-service", {})
            self.agent.create_security_group_relations(function_arn, output.get("VpcConfig"), "SecurityGroupIds")

        if function.Environment:
            for env in function.Environment.Variables.values():
                # Match on a fully formed RDS URI, optionally with port number
                if re.match(r".+\.[a-z0-9]{12}\.[a-z]{2}-([a-z]*-){1,2}\d\.rds\.amazonaws\.com(:\d{1,5})?$", env):
                    rds_arn = self.agent.create_arn(
                        "AWS::RDS::DBInstance", self.location_info, resource_id=env.split(".", 1)[0]
                    )
                    self.emit_relation(function_arn, rds_arn, "uses-service", {})

        # TODO also emit versions as components and relation to alias / canaries
        # https://stackstate.atlassian.net/browse/STAC-13113
        for alias_data in data.aliases:
            alias = FunctionAlias(alias_data, strict=False)
            alias.validate()
            alias_output = make_valid_data(alias_data)
            alias_output["Function"] = output
            self.emit_component(alias.AliasArn, ".".join([self.COMPONENT_TYPE, "alias"]), alias_output)
            if function.VpcConfig.VpcId:
                self.emit_relation(alias.AliasArn, function.VpcConfig.VpcId, "uses-service", {})

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
