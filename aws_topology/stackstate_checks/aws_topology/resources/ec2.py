from ..utils import make_valid_data, create_host_urn, create_resource_arn
import time
from .registry import RegisteredResource


class ec2(RegisteredResource):
    API = "ec2"
    COMPONENT_TYPE = "aws.ec2"

    def __init__(self, location_info, client, agent):
        RegisteredResource.__init__(self, location_info, client, agent)
        self.nitroInstances = None

    def process_all(self):
        ec2 = {}
        for reservation in self.client.describe_instances().get('Reservations') or []:
            for instance_data_raw in reservation.get('Instances') or []:
                instance_data = make_valid_data(instance_data_raw)
                if instance_data['State']['Name'] != "terminated":
                    result = self.process_instance(instance_data)
                    ec2.update(result)
        return ec2

    def process_instance(self, instance_data):
        if self.nitroInstances is None:
            instance_types = self.client.get_instance_types()['InstanceTypes']
            self.nitroInstances = list(filter(
                lambda instanceType: 'Hypervisor' not in instanceType or instanceType['Hypervisor'] == "nitro",
                instance_types
            ))
        instance_id = instance_data['InstanceId']
        instance_data['URN'] = [
            create_host_urn(instance_id),
            create_resource_arn(
                'ec2',
                self.location_info['AwsRegion'],
                self.location_info['AwsAccount'],
                'instance',
                instance_id)
        ]
        if instance_data.get('PublicDnsName') and instance_data.get('PublicDnsName') != "":
            instance_data['URN'].append(create_host_urn(instance_data['PublicDnsName']))
        if instance_data.get('PublicIpAddress') and instance_data.get('PublicIpAddress') != "":
            instance_data['URN'].append(create_host_urn(instance_data['PublicIpAddress']))
        instance_data['isNitro'] = False
        if instance_data['InstanceType'] in map(lambda x: x['InstanceType'], self.nitroInstances):
            instance_data['isNitro'] = True
        self.agent.component(instance_id, self.COMPONENT_TYPE, instance_data)

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
