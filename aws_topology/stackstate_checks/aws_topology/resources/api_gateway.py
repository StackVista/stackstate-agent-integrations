import re
from .utils import (
    set_required_access_v2,
    with_dimensions,
    make_valid_data,
    create_arn as arn,
    replace_stage_variables,
    transformation,
    client_array_operation,
)
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ModelType, DictType

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse


def create_api_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="execute-api", region=region, account_id=account_id, resource_id=resource_id)


def create_stage_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="execute-api", region=region, account_id=account_id, resource_id=resource_id)


def create_resource_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="execute-api", region=region, account_id=account_id, resource_id=resource_id)


def create_method_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="execute-api", region=region, account_id=account_id, resource_id=resource_id)


class Api(Model):
    id = StringType(required=True)
    name = StringType(default="UNKNOWN")


class ResourceMethod(Model):
    class ResourceMethodIntegration(Model):
        type = StringType(default="UNKNOWN")
        uri = StringType(required=True)

    httpMethod = StringType()
    methodIntegration = ModelType(ResourceMethodIntegration)


class Resource(Model):
    id = StringType(required=True)
    path = StringType(required=True)
    pathPart = StringType(default=None)
    resourceMethods = DictType(ModelType(ResourceMethod), default={})


class Stage(Model):
    deploymentId = StringType(required=True)
    stageName = StringType(default="UNKNOWN")
    variables = DictType(StringType, default={})
    tags = DictType(StringType, default={})


ApiData = namedtuple("ApiData", ["api", "stages", "resources"])


class ApigatewayStageCollector(RegisteredResourceCollector):
    API = "apigateway"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.apigateway.stage"

    @set_required_access_v2("apigateway:GET")
    def collect_methods(self, resource_data, rest_api_id):
        for method in resource_data.get("resourceMethods", {}).keys():
            # The boto3 docs suggest that methods are returned in the get_resources call; this is a lie.
            if not resource_data["resourceMethods"][method]:
                resource_data["resourceMethods"][method] = (
                    self.client.get_method(restApiId=rest_api_id, resourceId=resource_data.get("id"), httpMethod=method)
                    or {}
                )
        return resource_data

    @set_required_access_v2("apigateway:GET")
    def collect_resources(self, rest_api_id):
        return [
            self.collect_methods(resource, rest_api_id)
            for resource in client_array_operation(self.client, "get_resources", "items", restApiId=rest_api_id)
        ] or []

    @set_required_access_v2("apigateway:GET")
    def collect_stages(self, rest_api_id):
        return self.client.get_stages(restApiId=rest_api_id).get("item", [])

    def collect_rest_api(self, rest_api_data):
        rest_api_id = rest_api_data.get("id", "")
        stages = self.collect_stages(rest_api_id)
        resources = self.collect_resources(rest_api_id)
        return ApiData(api=rest_api_data, stages=stages, resources=resources)

    def collect_rest_apis(self):
        for rest_api in [
            self.collect_rest_api(rest_api_data)
            for rest_api_data in client_array_operation(self.client, "get_rest_apis", "items")
        ]:
            yield rest_api

    @set_required_access_v2("apigateway:GET")
    def process_rest_apis(self):
        for rest_api_data in self.collect_rest_apis():
            self.process_rest_api(rest_api_data)

    def process_all(self, filter=None):
        if not filter or "apis" in filter:
            self.process_rest_apis()

    @transformation()
    def process_resource_method(self, data, method, resource, stage, api, stage_arn, resource_arn):
        if method.methodIntegration and method.methodIntegration.type in ["AWS_PROXY", "AWS", "HTTP_PROXY"]:
            method_data = make_valid_data(data)
            method_arn = "{}/{}{}".format(stage_arn, method.httpMethod, resource.path)
            method_data.update(
                {
                    "ResourceId": resource.id,
                    "Path": resource.path,
                    "PathPart": resource.pathPart,
                    "DeploymentId": stage.deploymentId,
                    "StageName": stage.stageName,
                    "RestApiId": api.id,
                    "RestApiName": api.name,
                }
            )
            method_data.update(
                with_dimensions(
                    [
                        {"key": "Method", "value": method.httpMethod},
                        {"key": "Resource", "value": resource.path},
                        {"key": "Stage", "value": stage.stageName},
                        {"key": "ApiName", "value": api.name},
                    ]
                )
            )
            method_integration_uri = replace_stage_variables(method.methodIntegration.uri, stage.variables)
            method_data["methodIntegration"]["uri"] = method_integration_uri

            if method.methodIntegration.type == "AWS_PROXY":
                integration_arn = method_integration_uri[
                    method_integration_uri.rfind("arn") : method_integration_uri.find("/invocations")
                ]
                self.emit_relation(method_arn, integration_arn, "uses service", {})
            elif re.match("arn:aws:apigateway:.+:sqs:path/.+", method_integration_uri):
                queue_arn = arn(
                    resource="sqs",
                    region=method_integration_uri.split(":", 4)[3],
                    account_id=method_integration_uri.split("/", 2)[1],
                    resource_id=method_integration_uri.rsplit("/", 1)[-1],
                )
                self.emit_relation(method_arn, queue_arn, "uses service", {})

            # Creates a dummy service component that is connected to the api gateway method
            # this dummy service component will merge with a real trace service
            if method.methodIntegration.type == "HTTP_PROXY":
                parsed_uri = urlparse(method.methodIntegration.uri)
                service_integration_urn = "urn:service:/{0}".format(parsed_uri.hostname)
                self.emit_component(service_integration_urn, "aws.apigateway.method.http.integration", {})
                self.emit_relation(method_arn, service_integration_urn, "uses service", {})

            self.emit_component(method_arn, "aws.apigateway.method", method_data)
            self.emit_relation(resource_arn, method_arn, "uses service", {})

    @transformation()
    def process_resource(self, data, stage, api, stage_arn):
        resource = Resource(data, strict=False)
        resource.validate()
        if resource.resourceMethods:
            resource_arn = "{}/*{}".format(stage_arn, resource.path)
            resource_data = {
                "ResourceId": resource.id,
                "Path": resource.path,
                "PathPart": resource.pathPart,
                "DeploymentId": stage.deploymentId,
                "StageName": stage.stageName,
                "RestApiId": api.id,
                "RestApiName": api.name,
            }
            resource_data.update(
                with_dimensions(
                    [
                        {"key": "Stage", "value": stage.stageName},
                        {"key": "ApiName", "value": api.name},
                    ]
                )
            )
            self.emit_component(resource_arn, "aws.apigateway.resource", resource_data)
            self.emit_relation(stage_arn, resource_arn, "uses service", {})

            for method_id in resource.resourceMethods.keys():
                self.process_resource_method(
                    data["resourceMethods"][method_id],
                    method=resource.resourceMethods[method_id],
                    resource=resource,
                    stage=stage,
                    api=api,
                    stage_arn=stage_arn,
                    resource_arn=resource_arn,
                )

    @transformation()
    def process_stage(self, data, api, resources, rest_api_arn):
        stage = Stage(data, strict=False)
        stage.validate()
        stage_arn = "arn:aws:execute-api:{}:{}:{}/{}".format(
            self.location_info.Location.AwsRegion,
            self.location_info.Location.AwsAccount,
            api.id,
            stage.stageName,
        )
        stage_data = {
            "DeploymentId": stage.deploymentId,
            "StageName": stage.stageName,
            "RestApiId": api.id,
            "RestApiName": api.name,
        }
        stage_data.update(
            with_dimensions(
                [
                    {"key": "Stage", "value": stage.stageName},
                    {"key": "ApiName", "value": api.name},
                ]
            )
        )
        if stage.tags:
            stage_data["tags"] = stage.tags

        self.emit_component(stage_arn, self.COMPONENT_TYPE, stage_data)
        self.emit_relation(rest_api_arn, stage_arn, "has resource", {})

        for resource in resources:
            self.process_resource(resource, stage=stage, api=api, stage_arn=stage_arn)

    @transformation()
    def process_rest_api(self, data):
        api = Api(data.api, strict=False)
        api.validate()
        rest_api_arn = self.agent.create_arn("AWS::ApiGateway::RestApi", self.location_info, api.id)
        rest_api_data = {"RestApiId": api.id, "RestApiName": api.name}
        self.emit_component(rest_api_arn, "aws.apigateway", rest_api_data)

        for stage in data.stages:
            self.process_stage(stage, api=api, resources=data.resources, rest_api_arn=rest_api_arn)
