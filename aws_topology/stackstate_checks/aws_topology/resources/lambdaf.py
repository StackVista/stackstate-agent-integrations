import time
from botocore.exceptions import ClientError
from .utils import make_valid_data, create_arn as arn
from .registry import RegisteredResourceCollector


def create_arn(resource_id, region, account_id, **kwargs):
    return arn(resource="lambda", region=region, account_id=account_id, resource_id="function:" + resource_id)


class LambdaCollector(RegisteredResourceCollector):
    API = "lambda"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.lambda"

    def process_all(self, filter=None):
        if not filter or "functions" in filter:
            self.process_functions()
        if not filter or "mappings" in filter:
            self.process_event_source_mappings()

    def process_functions(self):
        for page in self.client.get_paginator("list_functions").paginate():
            for function_data_raw in page.get("Functions") or []:
                function_data = make_valid_data(function_data_raw)
                self.process_lambda(function_data)

    def process_one_function(self, name):
        function_data_raw = self.client.get_function(FunctionName=name).get("Configuration")
        function_data = make_valid_data(function_data_raw)
        self.process_lambda(function_data)

    def process_event_source_mappings(self):
        for page in self.client.get_paginator("list_event_source_mappings").paginate():
            for event_source_raw in page.get("EventSourceMappings") or []:
                event_source = make_valid_data(event_source_raw)
                if event_source["State"] == "Enabled":
                    self.process_event_source(event_source)

    def process_event_source(self, event_source):
        source_id = event_source["EventSourceArn"]
        target_id = event_source["FunctionArn"]
        # Swapping source/target: StackState models dependencies, not data flow
        self.emit_relation(target_id, source_id, "uses service", event_source)

    def process_lambda(self, function_data):
        function_arn = function_data["FunctionArn"]
        function_tags = None
        while function_tags is None:
            try:
                function_tags = self.client.list_tags(Resource=function_arn).get("Tags") or []
            except ClientError as exception_obj:
                if exception_obj.response["Error"]["Code"] == "ThrottlingException":
                    time.sleep(4)
                    pass
        function_data["Tags"] = function_tags
        self.emit_component(function_arn, self.COMPONENT_TYPE, function_data)
        lambda_vpc_config = function_data.get("VpcConfig")
        vpc_id = None
        if lambda_vpc_config:
            vpc_id = lambda_vpc_config["VpcId"]
            if vpc_id:
                self.emit_relation(function_arn, vpc_id, "uses service", {})
            self.agent.create_security_group_relations(function_arn, lambda_vpc_config, "SecurityGroupIds")
        # TODO also emit versions as components and relation to alias / canaries
        # https://stackstate.atlassian.net/browse/STAC-13113
        for alias_data in self.client.list_aliases(FunctionName=function_arn).get("Aliases") or []:
            alias_data["Function"] = function_data
            alias_arn = alias_data["AliasArn"]
            self.emit_component(alias_arn, "aws.lambda.alias", alias_data)
            if vpc_id:
                self.emit_relation(alias_arn, vpc_id, "uses service", {})

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
