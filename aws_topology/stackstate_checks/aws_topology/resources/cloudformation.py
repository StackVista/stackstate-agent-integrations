from ..utils import make_valid_data
from .registry import RegisteredResourceCollector

# TODO memorydata
memory_data = {}

type_map = {
    'AWS::Lambda::Function': 'lambda_func',
    'AWS::Kinesis::Stream': 'kinesis_stream',
    'AWS::S3::Bucket': 's3',
    'AWS::ElasticLoadBalancingV2::TargetGroup': 'target_group',
    'AWS::ElasticLoadBalancingV2::LoadBalancer': 'load_balancer',
    'AWS::AutoScaling::AutoScalingGroup': 'auto_scaling',
    'AWS::ElasticLoadBalancing::LoadBalancer': 'elb_classic',
    'AWS::RDS::DBInstance': 'rds',
    'AWS::SNS::Topic': 'sns',
    'AWS::SQS::Queue': 'sqs',
    'AWS::DynamoDB::Table': 'dynamodb',
    'AWS::ECS::Cluster': 'ecs_cluster',
    'AWS::EC2::Instance': 'ec2'
}


class CloudFormation_Collector(RegisteredResourceCollector):
    API = "cloudformation"
    COMPONENT_TYPE = "aws.cloudformation"

    def process_all(self, memory_data=None):
        self.memory_data = memory_data
        for stack_description_raw in self.client.describe_stacks().get('Stacks') or []:
            stack_description = make_valid_data(stack_description_raw)
            stack_id = stack_description['StackId']
            stack_name = stack_description["StackName"]
            self.process_stack(stack_id, stack_name, stack_description)
        for stack_data_page in self.client.get_paginator('list_stacks').paginate():
            for stack_raw in stack_data_page.get('StackSummaries') or []:
                stack = make_valid_data(stack_raw)
                stack_id = stack['StackId']
                if 'ParentId' not in stack:
                    continue
                parent_id = stack['ParentId']
                self.agent.relation(stack_id, parent_id, 'child of', stack)

    def process_stack(self, stack_id, stack_name, stack_description):
        self.agent.component(stack_id, self.COMPONENT_TYPE, stack_description)
        self.process_resources(stack_id, stack_name)

    def process_resources(self, stack_id, stack_name):
        # TODO StackName can also be sent stack_id
        resources = self.client.describe_stack_resources(StackName=stack_name).get('StackResources') or []
        for resource in resources:
            self.process_resource(stack_id, resource)

    def process_resource(self, stack_id, resource):
        resource_type = resource['ResourceType']
        mapped_type = type_map.get(resource_type)
        if mapped_type is not None:
            self.create_relation(stack_id, mapped_type, resource)
        elif resource_type == 'AWS::ApiGateway::RestApi':
            # api stage data is an array because of same api_id for multiple stages
            for api in self.memory_data.get('api_stage') or []:
                if api.get(resource.get('PhysicalResourceId')):
                    self.agent.relation(stack_id, api.get(resource['PhysicalResourceId']), 'has resource', {})

    def create_relation(self, stack_id, resource_type, resource_data):
        resource_type_ids = self.memory_data.get(resource_type)
        if resource_type_ids:
            physical_id = resource_data.get('PhysicalResourceId')
            if physical_id:
                target_id = resource_type_ids.get(physical_id)
                if target_id:
                    self.agent.relation(stack_id, target_id, 'has resource', {})
                # TODO else:
                #    self.logger.warning('%s %s with physical resource id %s not found.',
                #                        resource_type, resource_data.get('LogicalResourceId'), physical_id)
            # TODO else:
            #    self.logger.warning('%s %s has no physical resource id.',
            #                        resource_type, resource_data.get('LogicalResourceId'))
