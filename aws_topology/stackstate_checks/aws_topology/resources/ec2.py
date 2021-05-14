import time
from .utils import make_valid_data, create_host_urn, create_resource_arn, create_hash
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType, ListType, BooleanType


class Tag(Model):
    Key = StringType(required=True)
    Value = StringType(required=True)


class Subnet(Model):
    SubnetId = StringType(required=True)
    Tags = ListType(ModelType(Tag), default=[])
    AvailabilityZone = StringType(required=True)
    VpcId = StringType(required=True)


class Vpc(Model):
    VpcId = StringType(required=True)
    IsDefault = BooleanType(default=False)
    Tags = ListType(ModelType(Tag), default=[])


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
        subnet_descriptions = self.client.describe_subnets().get('Subnets') or []

        # Create all vpc
        for vpc_description in vpc_descriptions:
            self.process_vpc(vpc_description)

        # Create all subnet components
        for subnet_description_raw in subnet_descriptions:
            self.process_subnet(subnet_description_raw)

    def process_vpc(self, vpc_description):
        output = make_valid_data(vpc_description)
        vpc = Vpc(vpc_description, strict=False)
        vpc.validate()
        # construct a name
        vpc_name = vpc.VpcId
        name_tag = [tag for tag in vpc.Tags if tag.Key == "Name"]
        if vpc.IsDefault:
            vpc_name = 'default'
        elif len(name_tag) > 0:
            vpc_name = name_tag[0].Value
        output["Name"] = vpc_name
        # add a URN
        output['URN'] = [
            create_resource_arn(
                'ec2',
                self.location_info['Location']['AwsRegion'],
                self.location_info['Location']['AwsAccount'],
                'vpc',
                vpc.VpcId
            )
        ]
        self.emit_component(vpc.VpcId, "aws.vpc", output)

    def process_subnet(self, subnet_description):
        output = make_valid_data(subnet_description)
        subnet = Subnet(subnet_description, strict=False)
        subnet.validate()
        # construct a name
        subnet_name = subnet.SubnetId
        name_tag = [tag for tag in subnet.Tags if tag.Key == "Name"]
        if len(name_tag) > 0:
            subnet_name = name_tag[0].Value
        if subnet.AvailabilityZone:
            subnet_name = '{}-{}'.format(subnet_name, subnet.AvailabilityZone)
        output['Name'] = subnet_name
        # add a URN
        output['URN'] = [
            create_resource_arn(
                'ec2',
                self.location_info['Location']['AwsRegion'],
                self.location_info['Location']['AwsAccount'],
                'subnet',
                subnet.SubnetId
            )
        ]
        self.emit_component(subnet.SubnetId, 'aws.subnet', output)
        self.agent.relation(subnet.SubnetId, subnet.VpcId, 'uses service', {})

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
