import time
from .utils import make_valid_data, create_host_urn, create_resource_arn, create_hash
from .registry import RegisteredResourceCollector


class Ec2InstanceCollector(RegisteredResourceCollector):
    API = "ec2"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.ec2"

    def __init__(self, location_info, client, agent):
        RegisteredResourceCollector.__init__(self, location_info, client, agent)
        self.nitroInstances = None

    def process_all(self, filter=None):
        if not filter or "instances" in filter:
            self.process_instances()
        if not filter or "security_groups" in filter:
            self.process_security_groups()
        if not filter or "vpcs" in filter:
            self.process_vpcs()
        if not filter or "vpn_gateways" in filter:
            self.process_vpn_gateways()

    def process_instances(self):
        for reservation in self.client.describe_instances().get('Reservations') or []:
            for instance_data_raw in reservation.get('Instances') or []:
                instance_data = make_valid_data(instance_data_raw)
                if instance_data['State']['Name'] != "terminated":
                    self.process_instance(instance_data)

    def process_instance(self, instance_data):
        if self.nitroInstances is None:
            instance_types = self.client.describe_instance_types()['InstanceTypes']
            self.nitroInstances = list(filter(
                lambda instance_type: 'Hypervisor' not in instance_type or instance_type['Hypervisor'] == "nitro",
                instance_types
            ))
        instance_id = instance_data['InstanceId']
        instance_data['URN'] = [
            create_host_urn(instance_id),
            create_resource_arn(
                'ec2',
                self.location_info['Location']['AwsRegion'],
                self.location_info['Location']['AwsAccount'],
                'instance',
                instance_id)
        ]

        if 'Tags' not in instance_data:
            instance_data['Tags'] = []
        instance_data['Tags'].append({'Key': 'host', 'Value': instance_id})
        instance_data['Tags'].append({'Key': 'instance-id', 'Value': instance_id})
        if instance_data.get('PrivateIpAddress') and instance_data.get('PrivateIpAddress') != "":
            instance_data['Tags'].append({'Key': 'private-ip', 'Value': instance_data['PrivateIpAddress']})
        if instance_data.get('PublicDnsName') and instance_data.get('PublicDnsName') != "":
            instance_data['Tags'].append({'Key': 'fqdn', 'Value': instance_data['PublicDnsName']})
            instance_data['URN'].append(create_host_urn(instance_data['PublicDnsName']))
        if instance_data.get('PublicIpAddress') and instance_data.get('PublicIpAddress') != "":
            instance_data['Tags'].append({'Key': 'public-ip', 'Value': instance_data['PublicIpAddress']})
            instance_data['URN'].append(create_host_urn(instance_data['PublicIpAddress']))

        instance_data['isNitro'] = False
        if instance_data['InstanceType'] in map(lambda x: x['InstanceType'], self.nitroInstances):
            instance_data['isNitro'] = True
        self.emit_component(instance_id, self.COMPONENT_TYPE, instance_data)

        # Map the subnet and if not available then map the VPC
        if instance_data.get('SubnetId'):
            self.agent.relation(instance_id, instance_data['SubnetId'], 'uses service', {})
        elif instance_data.get('VpcId'):
            self.agent.relation(instance_id, instance_data['VpcId'], 'uses service', {})

        if instance_data.get('SecurityGroups'):
            for security_group in instance_data['SecurityGroups']:
                self.agent.relation(instance_id, security_group['GroupId'], 'uses service', {})

        event = {
            'timestamp': int(time.time()),
            'event_type': 'ec2_state',
            'msg_title': 'EC2 instance state',
            'msg_text': instance_data['State']['Name'],
            'host': instance_id,
            'tags': [
                "state:" + instance_data['State']['Name']
            ]
        }
        self.agent.event(event)
        return {instance_id: instance_id}

    def process_security_groups(self):
        for group_data_raw in self.client.describe_security_groups().get('SecurityGroups') or []:
            group_data = make_valid_data(group_data_raw)
            self.process_security_group(group_data)

    def process_security_group(self, group_data):
        group_id = group_data['GroupId']
        group_data['Version'] = create_hash(group_data)
        group_data['Name'] = group_data['GroupName']
        group_data['URN'] = [
            create_resource_arn(
                'ec2',
                self.location_info['Location']['AwsRegion'],
                self.location_info['Location']['AwsAccount'],
                'security-group', group_id
            )
        ]

        self.emit_component(group_id, "aws.security-group", group_data)

        if group_data.get('VpcId'):
            self.agent.relation(group_data['VpcId'], group_id, 'has resource', {})

    def process_vpcs(self):
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
            self.emit_component(subnet_id, 'aws.subnet', subnet_description)

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
        self.emit_component(vpc_id, "aws.vpc", vpc_description)
        subnets_for_vpc = list(filter(lambda subnet: subnet['VpcId'] == vpc_id, subnet_descriptions))
        for subnet_for_vpc in subnets_for_vpc:
            self.agent.relation(subnet_for_vpc['SubnetId'], vpc_id, 'uses service', {})

    def process_vpn_gateways(self):
        for vpn_description_raw in self.client.describe_vpn_gateways().get('VpnGateways') or []:
            vpn_description = make_valid_data(vpn_description_raw)
            self.process_vpn_gateway(vpn_description)

    def process_vpn_gateway(self, vpn_description):
        vpn_id = vpn_description['VpnGatewayId']
        self.emit_component(vpn_id, "aws.vpngateway", vpn_description)
        if vpn_description.get('VpcAttachments'):
            for vpn_attachment in vpn_description['VpcAttachments']:
                vpc_id = vpn_attachment['VpcId']
                self.agent.relation(vpn_id, vpc_id, 'uses service', {})
