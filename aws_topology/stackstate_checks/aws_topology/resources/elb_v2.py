from ..utils import make_valid_data, correct_tags, with_dimensions, extract_dimension_name, \
    update_dimensions, create_security_group_relations
import time


# application & network load balancer
def process_elb_v2(location_info, client, agent):
    result = {}
    target_group = {}
    load_balancer = {}
    lb_type = {}
    for elb_data_raw in client.describe_load_balancers().get('LoadBalancers') or []:
        elb_data = make_valid_data(elb_data_raw)
        elb_external_id = elb_data['LoadBalancerArn']
        # can become 1 call!
        elb_tags = client.describe_tags(
            ResourceArns=[elb_external_id]
        ).get('TagDescriptions') or [{'Tags': []}][0]['Tags']
        elb_type = "aws.elb_v2_" + elb_data['Type'].lower()
        elb_data['Tags'] = elb_tags
        elb_data['Name'] = elb_data['LoadBalancerName']
        elb_data['listeners'] = []

        elb_data.update(with_dimensions([{
            'Key': 'LoadBalancer',
            'Value': extract_dimension_name(elb_external_id, 'loadbalancer')
        }]))
        vpc_id = elb_data['VpcId']

        elb_data.update(location_info)

        create_security_group_relations(elb_external_id, elb_data, agent)

        for listener_raw in client.describe_listeners(
            LoadBalancerArn=elb_data["LoadBalancerArn"]
        ).get("Listeners") or []:
            listener = make_valid_data(listener_raw)
            elb_data['listeners'].append(listener)

        agent.component(elb_external_id, elb_type, correct_tags(elb_data))
        load_balancer[elb_external_id] = elb_external_id
        lb_type[elb_external_id] = elb_data['Type'].lower()
        agent.relation(elb_external_id, vpc_id, 'uses service', {})
    result['load_balancer'] = load_balancer

    for target_group_data_raw in client.describe_target_groups().get('TargetGroups') or []:
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
        target_group_data.update(location_info)

        agent.component(target_group_external_id, 'aws.elb_v2_target_group', correct_tags(target_group_data))
        target_group[target_group_external_id] = target_group_external_id

        agent.relation(target_group_external_id, vpc_id, 'uses service')

        for elb_arn in target_group_data['LoadBalancerArns']:
            elb_target_group_data = {}
            elb_target_group_data.update(location_info)

            agent.relation(elb_arn, target_group_external_id, 'uses service', elb_target_group_data)

        for target_raw in client.describe_target_health(
            TargetGroupArn=target_group_data['TargetGroupArn']
        ).get('TargetHealthDescriptions') or []:
            target = make_valid_data(target_raw)
            # assuming instance here, IP is another option
            target_external_id = target['Target']['Id']

            target_data = target
            target_data['Name'] = target_external_id
            target_data.update(location_info)
            target_data['URN'] = [
                # This id will match the EC2 instance
                target_external_id
            ]

            # Adding urn:aws/ to make it unique from the EC2 instance id
            agent.component("urn:aws/target-group-instance/" + target_external_id,
                            'aws.elb_v2_target_group_instance',
                            correct_tags(target_data))

            # relation between target group and target
            agent.relation(target_group_external_id,
                           "urn:aws/target-group-instance/" + target_external_id,
                           'uses service',
                           {})

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

            agent.event(event)
    result['target_group'] = target_group
    return result
