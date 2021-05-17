from .utils import make_valid_data, create_arn as arn, client_array_operation
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType

def create_httpapi_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='execute-api', region=region, account_id=account_id, resource_id=resource_id)


def create_httpapi_endpoint(api_id, region):
    return "https://{}.execute-api.{}.amazonaws.com".format(api_id, region)


class Api(Model):
    ApiId = StringType(required=True)


class Stage(Model):
    DeploymentId = StringType()
    StageName = StringType(default="UNKNOWN")


class Route(Model):
    Target = StringType(default='')


ApiData = namedtuple('ApiData', ['summary', 'stages', 'routes', 'integrations'])


class ApigatewayV2Collector(RegisteredResourceCollector):
    API = "apigatewayv2"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.httpapi"

    def collect_stages(self, api_id):
        return [stage for stage in client_array_operation(
            self.client,
            'get_stages',
            'Items',
            ApiId=api_id
        )]

    def collect_routes(self, api_id):
        return [route for route in client_array_operation(
            self.client,
            'get_routes',
            'Items',
            ApiId=api_id
        )]

    def collect_integrations(self, api_id):
        return {
            integration.get('IntegrationId'): integration
            for integration in client_array_operation(
                self.client,
                'get_integrations',
                'Items',
                ApiId=api_id
            )
        }

    def collect_api(self, api_summary):
        api_id = api_summary.get('ApiId')
        stages = self.collect_stages(api_id) or []
        routes = self.collect_routes(api_id) or []
        integrations = self.collect_integrations(api_id) or []
        return ApiData(summary=api_summary, stages=stages, routes=routes, integrations=integrations)

    def collect_apis(self):
        for api in [
                self.collect_api(api_summary) for api_summary in client_array_operation(
                    self.client,
                    'get_apis',
                    'Items'
                )
        ]:
            yield api

    def process_all(self, filter=None):
        for api in self.collect_apis():
            self.process_api(api)

    def process_api(self, api_data):
        api = Api(api_data.summary, strict=False)
        api.validate()
        output = make_valid_data(api_data.summary)
        api_arn = self.agent.create_arn(
            'AWS::ApiGatewayV2::Api',
            self.location_info,
            api.ApiId
        )
        self.emit_component(api_arn, 'aws.httpapi', output)
        for stage in api_data.stages or []:
            if self.process_stage(api_arn, stage):
                for route in api_data.routes:
                    self.process_route(route, api_data.integrations)

    def process_stage(self, api_arn, stage_data):
        output = make_valid_data(stage_data)
        stage = Stage(stage_data, strict=False)
        stage.validate()
        if stage.DeploymentId:
            output["Name"] = stage.StageName
            stage_arn = api_arn + '/' + stage.StageName
            self.emit_component(stage_arn, 'aws.httpapi.stage', output)
            self.agent.relation(api_arn, stage_arn, 'has resource', {})
            return True
        return False

    def process_route(self, route_data, integrations):
        route = Route(route_data, strict=False)
        route.validate()
        target = route.Target.split('/')
        if len(target) > 1 and integrations[target[-1]]:
            pass
            # Lambda
            # SQS
            # Private resource in VPC
            # HTTP 
            # EventBridge
            # Kinesis
            # StepFunctions
            # AppConfig
            # print(
            #    stage.get('StageName'),
            #   route.get('RouteKey'),
            #   target[-1],
            #   integrations[target[-1]])
            # Integration can be Lambda, HTTP URI, Private Resource in VPC,
            #   EventBridge, SQS, AppConfig, Kinesis, StepFunction

