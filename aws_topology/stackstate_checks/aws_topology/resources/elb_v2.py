from .utils import make_valid_data, with_dimensions, extract_dimension_name, \
    update_dimensions, create_security_group_relations
import time
from .registry import RegisteredResourceCollector


class ElbV2Collector(RegisteredResourceCollector):
    API = "elbv2"
    COMPONENT_TYPE = "aws.elb_v2"
    MEMORY_KEY = "MULTIPLE"

    def process_all(self):
        result = {}
        load_balancer = {}
        lb_type = {}
        for elb_data_raw in self.client.describe_load_balancers().get('LoadBalancers') or []:
            elb_data = make_valid_data(elb_data_raw)
            elb_external_id = elb_data['LoadBalancerArn']
            # can become 1 call!
            elb_tags = self.client.describe_tags(ResourceArns=[elb_external_id]).get('TagDescriptions')
            if len(elb_tags) > 0:
                elb_tags = elb_tags[0].get('Tags') or []
            elb_type = "aws.elb_v2_" + elb_data['Type'].lower()
            elb_data['Tags'] = elb_tags
            elb_data['Name'] = elb_data['LoadBalancerName']
            elb_data['listeners'] = []

            elb_data.update(with_dimensions([{
                'Key': 'LoadBalancer',
                'Value': extract_dimension_name(elb_external_id, 'loadbalancer')
            }]))
            vpc_id = elb_data['VpcId']

            create_security_group_relations(elb_external_id, elb_data, self.agent)

            for listener_raw in self.client.describe_listeners(
                LoadBalancerArn=elb_data["LoadBalancerArn"]
            ).get("Listeners") or []:
                listener = make_valid_data(listener_raw)
                elb_data['listeners'].append(listener)

            self.agent.component(elb_external_id, elb_type, elb_data)
            load_balancer[elb_external_id] = elb_external_id
            lb_type[elb_external_id] = elb_data['Type'].lower()
            self.agent.relation(elb_external_id, vpc_id, 'uses service', {})
        result['load_balancer'] = load_balancer
        target_group = {}
        for target_group_data_raw in self.client.describe_target_groups().get('TargetGroups') or []:
            target_group_data = make_valid_data(target_group_data_raw)
            target_group_external_id = target_group_data['TargetGroupArn']
            vpc_id = target_group_data['VpcId']
            target_group_data['Name'] = target_group_data['TargetGroupName']
            target_group_data.update(with_dimensions([{
                'Key': 'TargetGroup',
                'Value': 'targetgroup/' + extract_dimension_name(target_group_external_id, 'targetgroup')
            }]))
            if len(target_group_data['LoadBalancerArns']) > 0:
                loadbalancer_arn = target_group_data['LoadBalancerArns'][0]
                elb_target_type = lb_type.get(loadbalancer_arn)
                if elb_target_type:
                    target_group_data["TargetLoadBalancerType"] = elb_target_type
                update_dimensions(target_group_data, {
                    'Key': 'LoadBalancer',
                    'Value': extract_dimension_name(loadbalancer_arn, 'loadbalancer')
                })

            self.agent.component(target_group_external_id, 'aws.elb_v2_target_group', target_group_data)
            target_group[target_group_external_id] = target_group_external_id

            self.agent.relation(target_group_external_id, vpc_id, 'uses service', {})

            for elb_arn in target_group_data['LoadBalancerArns']:
                elb_target_group_data = {}
                elb_target_group_data.update(self.location_info)

                self.agent.relation(elb_arn, target_group_external_id, 'uses service', elb_target_group_data)

            for target_raw in self.client.describe_target_health(
                TargetGroupArn=target_group_data['TargetGroupArn']
            ).get('TargetHealthDescriptions') or []:
                target = make_valid_data(target_raw)
                # assuming instance here, IP is another option
                target_external_id = target['Target']['Id']

                target_data = target
                target_data['Name'] = target_external_id
                target_data['URN'] = [
                    # This id will match the EC2 instance
                    target_external_id
                ]

                # Adding urn:aws/ to make it unique from the EC2 instance id
                self.agent.component(
                    "urn:aws/target-group-instance/" + target_external_id,
                    'aws.elb_v2_target_group_instance',
                    target_data
                )

                # relation between target group and target
                self.agent.relation(
                    target_group_external_id,
                    "urn:aws/target-group-instance/" + target_external_id,
                    'uses service',
                    {}
                )

                event = {
                    'timestamp': int(time.time()),
                    'event_type': 'target_instance_health',
                    'msg_title': 'Target instance health',
                    'msg_text': target_data['TargetHealth']['State'],
                    'host': target_data['Target']['Id'],
                    'tags': [
                        "state:" + target_data['TargetHealth']['State'],
                        "reason:" + str(target_data['TargetHealth'].get('Reason'))
                    ]
                }

                self.agent.event(event)
        result['target_group'] = target_group
        return result
