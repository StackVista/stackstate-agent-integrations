from ..utils import make_valid_data
from .registry import RegisteredResourceCollector


class AutoScaling_Collector(RegisteredResourceCollector):
    API = "autoscaling"
    COMPONENT_TYPE = "aws.autoscaling"
    MEMORY_KEY = "auto_scaling"

    def process_all(self):
        auto_scaling = {}
        for describe_auto_scaling_groups_page in self.client.get_paginator('describe_auto_scaling_groups').paginate():
            for auto_scaling_group_description_raw in describe_auto_scaling_groups_page.get('AutoScalingGroups') or []:
                auto_scaling_group_description = make_valid_data(auto_scaling_group_description_raw)
                result = self.process_autoscaling_group(auto_scaling_group_description)
                auto_scaling.update(result)
        return auto_scaling

    def process_autoscaling_group(self, auto_scaling_group_description):
        auto_scaling_group_arn = auto_scaling_group_description['AutoScalingGroupARN']
        auto_scaling_group_name = auto_scaling_group_description['AutoScalingGroupName']
        self.agent.component(auto_scaling_group_arn, self.COMPONENT_TYPE, auto_scaling_group_description)
        for instance in auto_scaling_group_description['Instances']:
            instance_id = instance['InstanceId']
            self.agent.relation(auto_scaling_group_arn, instance_id, 'uses service', {})

        for load_balancer_name in auto_scaling_group_description['LoadBalancerNames']:
            self.agent.relation('classic_elb_' + load_balancer_name, auto_scaling_group_arn, 'uses service', {})

            for instance in auto_scaling_group_description['Instances']:
                # removing elb instances if there are any
                instance_id = instance['InstanceId']
                relation_id = 'classic_elb_' + load_balancer_name + '-uses service-' + instance_id
                self.agent.delete(relation_id)

        for target_group_arn in auto_scaling_group_description['TargetGroupARNs']:
            self.agent.relation(target_group_arn, auto_scaling_group_arn, 'uses service', {})

            for instance in auto_scaling_group_description['Instances']:
                # removing elb instances if there are any
                instance_id = instance["InstanceId"]
                relation_id = target_group_arn + '-uses service-' + instance_id
                self.agent.delete(relation_id)
        return {auto_scaling_group_name: auto_scaling_group_arn}
