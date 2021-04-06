from ..utils import make_valid_data, correct_tags


def process_auto_scaling(location_info, client, agent):
    auto_scaling = {}
    for describe_auto_scaling_groups_page in client.get_paginator('describe_auto_scaling_groups').paginate():
        for auto_scaling_group_description_raw in describe_auto_scaling_groups_page.get('AutoScalingGroups') or []:
            auto_scaling_group_description = make_valid_data(auto_scaling_group_description_raw)
            auto_scaling_group_arn = auto_scaling_group_description['AutoScalingGroupARN']
            auto_scaling_group_description.update(location_info)
            auto_scaling_group_name = auto_scaling_group_description['AutoScalingGroupName']
            agent.component(auto_scaling_group_arn, 'aws.autoscaling',
                            correct_tags(auto_scaling_group_description))
            auto_scaling[auto_scaling_group_name] = auto_scaling_group_arn
            for instance in auto_scaling_group_description['Instances']:
                instance_id = instance['InstanceId']
                agent.relation(auto_scaling_group_arn, instance_id, 'uses service', {})

            for load_balancer_name in auto_scaling_group_description['LoadBalancerNames']:
                agent.relation('classic_elb_' + load_balancer_name, auto_scaling_group_arn, 'uses service', {})

                for instance in auto_scaling_group_description['Instances']:
                    # removing elb instances if there are any
                    instance_id = instance['InstanceId']
                    relation_id = 'classic_elb_' + load_balancer_name + '-uses service-' + instance_id
                    agent.delete(relation_id)

            for target_group_arn in auto_scaling_group_description['TargetGroupARNs']:
                agent.relation(target_group_arn, auto_scaling_group_arn, 'uses service', {})

                for instance in auto_scaling_group_description['Instances']:
                    # removing elb instances if there are any
                    instance_id = instance["InstanceId"]
                    relation_id = target_group_arn + '-uses service-' + instance_id
                    agent.delete(relation_id)
    return auto_scaling
