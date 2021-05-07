import copy
import re
from .utils import with_dimensions, make_valid_data, create_arn as arn, replace_stage_variables
from .registry import RegisteredResourceCollector
import json

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse


def create_httpapi_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='execute-api', region=region, account_id=account_id, resource_id=resource_id)


def create_httpapi_endpoint(api_id, region):
    return "https://{}.execute-api.{}.amazonaws.com".format(api_id, region)


class ApigatewayV2Collector(RegisteredResourceCollector):
    API = "apigatewayv2"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.httpapi"

    def process_all(self, filter=None):
        try:
            for apis_page in self.client.get_paginator('get_apis').paginate():
                for api in apis_page.get('Items') or []:
                    api_id = api.get('ApiId')
                    api_arn = self.agent.create_arn('AWS::ApiGatewayV2::Api', self.location_info, api_id)
                    self.emit_component(api_arn, 'aws.httpapi', make_valid_data(api))
                    stages = [
                        stage
                        for stage in self.client.get_stages(ApiId=api_id)['Items']
                    ]
                    routes = [
                        route
                        for api_resource_page in self.client.get_paginator(
                            'get_routes'
                        ).paginate(ApiId=api_id)
                        for route in api_resource_page['Items']
                    ]
                    integrations = {
                        integration.get('IntegrationId'): integration
                        for api_resource_page in self.client.get_paginator(
                            'get_integrations'
                        ).paginate(ApiId=api_id)
                        for integration in api_resource_page['Items']
                    }
                    # print('STAGES ', json.dumps(stages, indent=2, default=str))
                    # print('ROUTES ', json.dumps(routes, indent=2, default=str))  # Target = integration/${IntegrationId}
                    # print('INTEGRATIONS ', json.dumps(integrations, indent=2, default=str))  # IntegrationId
                    for stage in stages:
                        deployment_id = stage.get('DeploymentId')
                        if deployment_id:
                            stage_name = stage.get('StageName')
                            stage["Name"] = stage_name
                            stage_arn = self.agent.create_arn('AWS::ApiGatewayV2::Api', self.location_info, api_id + '/' + stage_name)
                            self.emit_component(stage_arn, 'aws.httpapi.stage', make_valid_data(stage))
                            self.agent.relation(api_arn, stage_arn, 'has resource', {})
                            for route in routes:
                                target = (route.get('Target') or '').split('/')
                                if len(target) > 1 and integrations[target[-1]]:
                                    pass
                                    # print(stage.get('StageName'), route.get('RouteKey'), target[-1], integrations[target[-1]])
                    # Integration can be Lambda, HTTP URI, Private Resource in VPC, EventBridge, SQS, AppConfig, Kinesis, StepFunction
        except Exception as e:
            print(e)
            raise e