import copy
import re
from ..utils import correct_tags, with_dimensions, make_valid_data, create_arn, replace_stage_variables

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse


def process_api_gateway(location_info, client, agent):
    # array because same rest_api_id can have multiple stages and cloudformation
    # takes rest_api_id as an Physical resource ID for the stack
    api_stage = []
    for rest_apis_page in client.get_paginator('get_rest_apis').paginate():
        for rest_api in rest_apis_page.get('items') or []:
            rest_api_id = rest_api['id']
            rest_api_data = {
                'RestApiId': rest_api['id'],
                'RestApiName': rest_api['name']
            }
            rest_api_data.update(location_info)

            stages = [
                stage
                for stage in client.get_stages(restApiId=rest_api_id)['item']
            ]
            resources = [
                resource
                for rest_api_resource_page in client.get_paginator('get_resources').paginate(restApiId=rest_api_id)
                for resource in rest_api_resource_page['items']
                if 'resourceMethods' in resource
            ]

            http_methods_per_resource = {
                resource['id']: [
                    method_details
                    for method_details in [
                        client.get_method(restApiId=rest_api_id, resourceId=resource['id'], httpMethod=http_method)
                        for http_method in resource['resourceMethods']
                    ]
                    if method_details.get('methodIntegration') and method_details['methodIntegration']['type']
                    in ['AWS_PROXY', 'AWS', 'HTTP_PROXY']
                ]
                for resource in resources
            }

            # send stages
            for stage in stages:
                stage_name = stage['stageName']
                stage_arn = 'arn:aws:execute-api:{}:{}:{}/{}'.format(
                    location_info['Location']['AwsRegion'],
                    location_info['Location']['AwsAccount'],
                    rest_api_id, stage_name
                )

                stage_data = {
                    'DeploymentId': stage['deploymentId'],
                    'StageName': stage_name
                }
                stage_data.update(rest_api_data)
                stage_data.update(with_dimensions([
                    {'key': 'Stage', 'value': stage_name},
                    {'key': 'ApiName', 'value': rest_api_data['RestApiName']}
                ]))

                agent.component(stage_arn, 'aws.apigateway.stage', correct_tags(stage_data))
                api_stage.append({rest_api_id: stage_arn})

                # send resources per stage
                for resource in resources:
                    resource_path = resource['path']
                    resource_arn = '{}/*{}'.format(stage_arn, resource_path)
                    resource_data = {
                        'ResourceId': resource['id'],
                        'Path': resource_path,
                        'PathPart': resource.get("pathPart", None)
                    }

                    resource_data.update(stage_data)
                    agent.component(resource_arn, 'aws.apigateway.resource', correct_tags(resource_data))
                    agent.relation(stage_arn, resource_arn, 'uses service', {})

                    # send methods per resource per stage
                    for method_raw in http_methods_per_resource[resource['id']]:
                        method = make_valid_data(method_raw)
                        method_arn = '{}/{}{}'.format(stage_arn, method['httpMethod'], resource_path)
                        method_data = copy.deepcopy(method)
                        method_data.update(resource_data)
                        method_data.update(with_dimensions([
                            {'key': 'Method', 'value': method['httpMethod']},
                            {'key': 'Resource', 'value': resource_data['Path']},
                            {'key': 'Stage', 'value': resource_data['StageName']},
                            {'key': 'ApiName', 'value': resource_data['RestApiName']}
                        ]))

                        method_integration_uri = replace_stage_variables(
                            method_data['methodIntegration']['uri'], stage['variables']
                        ) if 'variables' in stage else method_data['methodIntegration']['uri']
                        method_data['methodIntegration']['uri'] = method_integration_uri

                        integration_arn = None
                        if method_data['methodIntegration']['type'] == 'AWS_PROXY':
                            integration_arn = method_integration_uri[
                                method_integration_uri.rfind('arn'):method_integration_uri.find('/invocations')
                            ]
                        elif re.match("arn:aws:apigateway:.+:sqs:path/.+", method_integration_uri):
                            queue_name = method_integration_uri.rsplit('/', 1)[-1]
                            queue_arn = create_arn(
                                'sqs',
                                location_info['Location']['AwsRegion'],
                                location_info['Location']['AwsAccount'],
                                queue_name
                            )
                            integration_arn = queue_arn

                        agent.component(method_arn, 'aws.apigateway.method', correct_tags(method_data))
                        agent.relation(resource_arn, method_arn, 'uses service', {})

                        if integration_arn:
                            agent.relation(method_arn, integration_arn, 'uses service', {})

                        # Creates a dummy service component that is connected to the api gateway method
                        # this dummy service component will merge with a real trace service
                        if method_data['methodIntegration']['type'] == 'HTTP_PROXY':
                            parsed_uri = urlparse(method_data['methodIntegration']['uri'])
                            service_integration_urn = 'urn:service:/{0}'.format(parsed_uri.hostname)

                            agent.component(service_integration_urn, 'aws.apigateway.method.http.integration', {})
                            agent.relation(method_arn, service_integration_urn, 'uses service', {})

    return api_stage
