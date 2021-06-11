from collections import namedtuple
from .utils import (
    make_valid_data,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from schematics import Model
from schematics.types import StringType, ModelType
from .registry import RegisteredResourceCollector
from .s3 import create_arn as s3_arn
from .lambdaf import create_arn as lambda_arn
from .kinesis import create_arn as kinesis_arn
from .dynamodb import create_table_arn as dynamodb_table_arn
from .firehose import create_arn as firehose_arn
from .sns import create_arn as sns_arn
from .rds import create_cluster_arn, create_db_arn
from .sqs import create_arn as sqs_arn
from .ecs import create_cluster_arn as ecs_cluster_arn
from .api_gateway import create_api_arn, create_stage_arn, create_resource_arn, create_method_arn
from .elb_classic import create_arn as create_elb_arn
from .route53_domain import create_arn as route53_domain_arn
from .route53_hostedzone import create_arn as route53_hosted_zone_arn


type_map = {
    "AWS::Lambda::Function": "lambda_func",
    "AWS::Kinesis::Stream": "kinesis_stream",
    "AWS::S3::Bucket": "s3",
    "AWS::ElasticLoadBalancingV2::TargetGroup": "target_group",
    "AWS::ElasticLoadBalancingV2::LoadBalancer": "load_balancer",
    "AWS::AutoScaling::AutoScalingGroup": "auto_scaling",
    "AWS::ElasticLoadBalancing::LoadBalancer": "elb_classic",
    "AWS::RDS::DBInstance": "rds",
    "AWS::SNS::Topic": "sns",
    "AWS::SQS::Queue": "sqs",
    "AWS::DynamoDB::Table": "dynamodb",
    "AWS::ECS::Cluster": "ecs_cluster",
    "AWS::EC2::Instance": "ec2",
}


def no_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return resource_id


type_arn = {
    "AWS::Lambda::Function": lambda_arn,
    "AWS::Kinesis::Stream": kinesis_arn,
    "AWS::KinesisFirehose::DeliveryStream": firehose_arn,
    "AWS::S3::Bucket": s3_arn,
    "AWS::RDS::DBInstance": create_db_arn,
    "AWS::RDS::DBCluster": create_cluster_arn,
    "AWS::SNS::Topic": sns_arn,
    "AWS::SQS::Queue": sqs_arn,
    "AWS::DynamoDB::Table": dynamodb_table_arn,
    "AWS::ECS::Cluster": ecs_cluster_arn,
    "AWS::ECS::TaskDefinition": no_arn,
    "AWS::ApiGateway::RestApi": create_api_arn,
    "AWS::ApiGateway::Stage": create_stage_arn,
    "AWS::ApiGateway::Resource": create_resource_arn,
    "AWS::ApiGateway::Method": create_method_arn,
    "AWS::ElasticLoadBalancing::LoadBalancer": create_elb_arn,  # TODO odd one
    "AWS::Redshift::Cluster": no_arn,
    "AWS::EC2::Instance": no_arn,
    "AWS::EC2::SecurityGroup": no_arn,
    "AWS::EC2::Vpc": no_arn,
    "AWS::EC2::Subnet": no_arn,
    "AWS::ElasticLoadBalancingV2::TargetGroup": no_arn,
    "AWS::ElasticLoadBalancingV2::LoadBalancer": no_arn,
    "AWS::AutoScaling::AutoScalingGroup": no_arn,
    "AWS::StepFunctions::StateMachine": no_arn,
    "AWS::StepFunctions::Activity": no_arn,
    "AWS::Route53Domains::Domain": route53_domain_arn,
    "AWS::Route53::HostedZone": route53_hosted_zone_arn,
    "AWS::CloudFormation::Stack": no_arn,
}


StackData = namedtuple("StackData", ["stack", "resources"])


class StackResource(Model):
    ResourceType = StringType(required=True)
    PhysicalResourceId = StringType()


class Stack(Model):
    StackId = StringType(required=True)
    StackName = StringType(required=True)
    ParentId = StringType()


class CloudformationCollector(RegisteredResourceCollector):
    API = "cloudformation"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.cloudformation"

    @set_required_access_v2("cloudformation:DescribeStackResources")
    def collect_stack_resources(self, stack_id):
        return self.client.describe_stack_resources(StackName=stack_id).get("StackResources", [])

    def collect_stack(self, stack_data):
        resources = self.collect_stack_resources(stack_data.get("StackId", ""))
        return StackData(stack=stack_data, resources=resources)

    def collect_stacks(self):
        for stack in [
            self.collect_stack(stack_data)
            for stack_data in client_array_operation(self.client, "describe_stacks", "Stacks")
        ]:
            yield stack

    @set_required_access_v2("cloudformation:DescribeStacks")
    def process_stacks(self):
        for stack_data in self.collect_stacks():
            self.process_stack(stack_data)

    def process_all(self, filter=None):
        if not filter or "stacks" in filter:
            self.process_stacks()

    @transformation()
    def process_stack(self, data):
        stack = Stack(data.stack, strict=False)
        stack.validate()
        output = make_valid_data(data.stack)
        output["Name"] = stack.StackName
        self.emit_component(stack.StackId, self.COMPONENT_TYPE, output)

        resources = [StackResource(resource, strict=False) for resource in data.resources]
        for resource in resources:
            resource.validate()
            if resource.PhysicalResourceId and resource.ResourceType in type_arn.keys():
                resource_arn = self.agent.create_arn(
                    resource.ResourceType, self.location_info, resource.PhysicalResourceId
                )
                self.emit_relation(stack.StackId, resource_arn, "has resource", {})
