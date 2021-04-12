from ..utils import make_valid_data
from .registry import RegisteredResourceCollector

# TODO memorydata
memory_data = {}


class CloudFormation_Collector(RegisteredResourceCollector):
    API = "cloudformation"
    COMPONENT_TYPE = "aws.cloudformation"

    def process_all(self):
        for stack_description_raw in self.client.describe_stacks().get('Stacks') or []:
            stack_description = make_valid_data(stack_description_raw)
            stack_id = stack_description['StackId']
            stack_name = stack_description["StackName"]
            self.process_stack(stack_id, stack_name, stack_description)

    def process_stack(self, stack_id, stack_name, stack_description):
        self.agent.component(stack_id, self.COMPONENT_TYPE, stack_description)
        resources = self.client.describe_stack_resources(StackName=stack_name).get('StackResources') or []
        for resource in resources:
            self.process_resource(stack_id, resource)

    def process_resource(self, stack_id, resource):
        if resource['ResourceType'] == 'AWS::Lambda::Function':
            self.create_relation(stack_id, 'lambda_func', resource)
        elif resource['ResourceType'] == 'AWS::Kinesis::Stream':
            self.create_relation(stack_id, 'kinesis_stream', resource)
        elif resource['ResourceType'] == 'AWS::S3::Bucket':
            self.create_relation(stack_id, 's3', resource)
        elif resource['ResourceType'] == 'AWS::ApiGateway::RestApi':
            # api stage data is an array because of same api_id for multiple stages
            for api in memory_data.get('api_stage') or []:
                if api.get(resource.get('PhysicalResourceId')):
                    self.agent.relation(stack_id, api.get(resource['PhysicalResourceId']), 'has resource', {})
        elif resource['ResourceType'] == 'AWS::ElasticLoadBalancingV2::TargetGroup':
            self.create_relation(stack_id, 'target_group', resource)
        elif resource['ResourceType'] == 'AWS::ElasticLoadBalancingV2::LoadBalancer':
            self.create_relation(stack_id, 'load_balancer', resource)
        elif resource['ResourceType'] == 'AWS::AutoScaling::AutoScalingGroup':
            self.create_relation(stack_id, 'auto_scaling', resource)
        elif resource['ResourceType'] == 'AWS::ElasticLoadBalancing::LoadBalancer':
            self.create_relation(stack_id, 'elb_classic', resource)
        elif resource['ResourceType'] == 'AWS::RDS::DBInstance':
            self.create_relation(stack_id, 'rds', resource)
        elif resource['ResourceType'] == 'AWS::SNS::Topic':
            self.create_relation(stack_id, 'sns', resource)
        elif resource['ResourceType'] == 'AWS::SQS::Queue':
            self.create_relation(stack_id, 'sqs', resource)
        elif resource['ResourceType'] == 'AWS::DynamoDB::Table':
            self.create_relation(stack_id, 'dynamodb', resource)
        elif resource['ResourceType'] == 'AWS::ECS::Cluster':
            self.create_relation(stack_id, 'ecs_cluster', resource)
        elif resource['ResourceType'] == 'AWS::EC2::Instance':
            self.create_relation(stack_id, 'ec2', resource)

    def create_relation(self, stack_id, resource_type, resource_data):
        resource_type_ids = memory_data.get(resource_type)
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
