import time
from .utils import make_valid_data, create_resource_arn
from .registry import RegisteredResourceCollector


class ELB_Classic_Collector(RegisteredResourceCollector):
    API = "elb"
    COMPONENT_TYPE = "aws.elb_classic"
    MEMORY_KEY = "elb_classic"

    def process_all(self):
        elb_classic = {}
        for elb_data_raw in self.client.describe_load_balancers().get('LoadBalancerDescriptions') or []:
            elb_data = make_valid_data(elb_data_raw)
            result = self.process_loadbalancer(elb_data)
            elb_classic.update(result)
        return elb_classic

    def process_loadbalancer(self, elb_data):
        elb_name = elb_data['LoadBalancerName']
        instance_id = 'classic_elb_' + elb_name
        elb_data['URN'] = [
            create_resource_arn(
                'elasticloadbalancing',
                self.location_info['Location']['AwsRegion'],
                self.location_info['Location']['AwsAccount'],
                'loadbalancer',
                elb_name
            )
        ]
        taginfo = self.client.describe_tags(LoadBalancerNames=[elb_name]).get('TagDescriptions')
        if taginfo and len(taginfo) > 0:
            tags = taginfo[0].get('Tags')
        if tags:
            elb_data['Tags'] = tags
        self.agent.component(instance_id, self.COMPONENT_TYPE, elb_data)

        vpc_id = elb_data['VPCId']
        self.agent.relation(instance_id, vpc_id, 'uses service', {})

        for instance in elb_data.get('Instances') or []:
            instance_external_id = instance['InstanceId']  # ec2 instance
            self.agent.relation(instance_id, instance_external_id, 'uses service', {})

        for instance_health in self.client.describe_instance_health(
            LoadBalancerName=elb_name
        ).get('InstanceStates') or []:
            event = {
                'timestamp': int(time.time()),
                'event_type': 'ec2_state',
                'msg_title': 'EC2 instance state',
                'msg_text': instance_health['State'],
                'host': instance_health['InstanceId'],
                'tags': [
                    "state:" + instance_health['State'],
                    "description:" + instance_health['Description']
                ]
            }
            self.agent.event(event)

        self.agent.create_security_group_relations(instance_id, elb_data)
        return {elb_name: instance_id}
