from ..utils import make_valid_data, correct_tags, create_resource_arn, create_hash


def process_security_group(location_info, client, agent):
    groups = {}
    for group_data_raw in client.describe_security_groups().get('SecurityGroups') or []:
        group_data = make_valid_data(group_data_raw)
        group_id = group_data['GroupId']
        group_data['Version'] = create_hash(group_data)
        group_data['Name'] = group_data['GroupName']
        group_data.update(location_info)
        group_data['URN'] = [
            create_resource_arn(
                'ec2',
                location_info['AwsRegion'],
                location_info['AwsAccount'],
                'security-group', group_id
            )
        ]

        agent.component(group_id, 'aws.security-group', correct_tags(group_data))
        groups[group_id] = group_id

        if group_data.get('VpcId'):
            agent.relation(group_data['VpcId'], group_id, 'has resource')

    if len(groups.keys()) > 0:
        return {'groups': groups}
    else:
        return None
