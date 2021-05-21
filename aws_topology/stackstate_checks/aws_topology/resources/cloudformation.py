from .utils import make_valid_data
from .registry import RegisteredResourceCollector
from .s3 import create_arn as s3_arn
from .lambdaf import create_arn as lambda_arn
from .kinesis import create_arn as kinesis_arn
from .dynamodb import create_table_arn as dynamodb_table_arn
from .firehose import create_arn as firehose_arn
from .rds import create_cluster_arn, create_db_arn
from .sqs import create_arn as sqs_arn
from .ecs import create_cluster_arn as ecs_cluster_arn
from .api_gateway import create_api_arn, create_stage_arn, create_resource_arn, create_method_arn
from .elb_classic import create_arn as create_elb_arn
from .api_gateway_v2 import create_httpapi_arn
from .eventbridge import create_event_bus_arn, create_rule_arn, create_archive_arn, create_replay_arn
from .iam import create_group_arn, create_user_arn, create_role_arn, create_instance_profile_arn


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


def no_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return resource_id


type_arn = {
    'AWS::Lambda::Function': lambda_arn,
    'AWS::Kinesis::Stream': kinesis_arn,
    'AWS::KinesisFirehose::DeliveryStream': firehose_arn,
    'AWS::S3::Bucket': s3_arn,
    'AWS::RDS::DBInstance': create_db_arn,
    'AWS::RDS::DBCluster': create_cluster_arn,
    'AWS::SNS::Topic': no_arn,  # TODO just removed
    'AWS::SQS::Queue': sqs_arn,
    'AWS::DynamoDB::Table': dynamodb_table_arn,
    'AWS::ECS::Cluster': ecs_cluster_arn,
    'AWS::ECS::TaskDefinition': no_arn,
    'AWS::ApiGateway::RestApi': create_api_arn,
    'AWS::ApiGateway::Stage': create_stage_arn,
    'AWS::ApiGateway::Resource': create_resource_arn,
    'AWS::ApiGateway::Method': create_method_arn,
    'AWS::ApiGatewayV2::Api': create_httpapi_arn,
    'AWS::ElasticLoadBalancing::LoadBalancer': create_elb_arn,  # TODO odd one
    'AWS::Events::EventBus': create_event_bus_arn,
    'AWS::Events::Rule': create_rule_arn,
    'AWS::Events::Archive': create_archive_arn,
    'AWS::Events::Replay': create_replay_arn,
    'AWS::Redshift::Cluster': no_arn,
    'AWS::EC2::Instance': no_arn,
    'AWS::EC2::SecurityGroup': no_arn,
    'AWS::EC2::Vpc': no_arn,
    'AWS::EC2::Subnet': no_arn,
    'AWS::ElasticLoadBalancingV2::TargetGroup': no_arn,
    'AWS::ElasticLoadBalancingV2::LoadBalancer': no_arn,
    'AWS::AutoScaling::AutoScalingGroup': no_arn,
    'AWS::IAM::Group': create_group_arn,
    'AWS::IAM::User': create_user_arn,
    'AWS::IAM::ManagedPolicy': no_arn,
    'AWS::IAM::Role': create_role_arn,
    'AWS::IAM::InstanceProfile': create_instance_profile_arn,
    "AWS::StepFunctions::StateMachine": no_arn,
    "AWS::StepFunctions::Activity": no_arn
}


class CloudformationCollector(RegisteredResourceCollector):
    API = "cloudformation"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.cloudformation"

    def process_all(self, filter=None):
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
        self.emit_component(stack_id, self.COMPONENT_TYPE, stack_description)
        self.process_resources(stack_id, stack_name)

    def process_resources(self, stack_id, stack_name):
        # TODO StackName can also be sent stack_id
        resources = self.client.describe_stack_resources(StackName=stack_name).get('StackResources') or []
        for resource in resources:
            self.process_resource(stack_id, resource)

    def process_resource(self, stack_id, resource):
        resource_type = resource['ResourceType']
        if resource.get('PhysicalResourceId'):
            arn = self.agent.create_arn(resource_type, self.location_info, resource.get('PhysicalResourceId'))
            self.agent.relation(stack_id, arn, 'has resource', {})
