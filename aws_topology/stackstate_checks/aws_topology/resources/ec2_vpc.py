from .utils import make_valid_data, create_resource_arn
from .registry import RegisteredResourceCollector


class VpcCollector(RegisteredResourceCollector):
    API = "ec2"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.vpc"

    def process_all(self):
        vpc_descriptions = self.client.describe_vpcs().get('Vpcs') or []
        vpc_ids = list(map(lambda vpc: vpc['VpcId'], vpc_descriptions))
        subnet_descriptions = self.client.describe_subnets(
            Filters=[{'Name': 'vpc-id', 'Values': vpc_ids}]
        ).get('Subnets') or []

        # Create all vpc
        for vpc_description in vpc_descriptions:
            self.process_vpc(vpc_description, subnet_descriptions)

        # Create all subnet components
        for subnet_description_raw in subnet_descriptions:
            subnet_description = make_valid_data(subnet_description_raw)
            subnet_id = subnet_description['SubnetId']
            subnet_description['URN'] = [
                create_resource_arn(
                    'ec2',
                    self.location_info['Location']['AwsRegion'],
                    self.location_info['Location']['AwsAccount'],
                    'subnet',
                    subnet_id
                )
            ]
            self.agent.component(subnet_id, 'aws.subnet', subnet_description)

    def process_vpc(self, vpc_description, subnet_descriptions):
        vpc_id = vpc_description['VpcId']
        vpc_description['URN'] = [
            create_resource_arn(
                'ec2',
                self.location_info['Location']['AwsRegion'],
                self.location_info['Location']['AwsAccount'],
                'vpc',
                vpc_id
            )
        ]
        self.agent.component(vpc_id, self.COMPONENT_TYPE, vpc_description)
        subnets_for_vpc = list(filter(lambda subnet: subnet['VpcId'] == vpc_id, subnet_descriptions))
        for subnet_for_vpc in subnets_for_vpc:
            self.agent.relation(subnet_for_vpc['SubnetId'], vpc_id, 'uses service', {})
