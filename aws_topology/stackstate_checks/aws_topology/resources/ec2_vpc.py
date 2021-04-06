from ..utils import make_valid_data, correct_tags, create_resource_arn


def process_vpcs(location_info, client, agent):
    vpc_descriptions = client.describe_vpcs().get('Vpcs') or []
    vpc_ids = list(map(lambda vpc: vpc['VpcId'], vpc_descriptions))
    subnet_descriptions = client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': vpc_ids}]).get('Subnets') or []

    # Create all vpc
    for vpc_description in vpc_descriptions:
        vpc_id = vpc_description['VpcId']
        vpc_description.update(location_info)
        vpc_description['URN'] = [
            create_resource_arn(
                'ec2',
                location_info['Location']['AwsRegion'],
                location_info['Location']['AwsAccount'],
                'vpc',
                vpc_id
            )
        ]

        agent.component(vpc_id, 'aws.vpc', correct_tags(vpc_description))

        subnets_for_vpc = list(filter(lambda subnet: subnet['VpcId'] == vpc_id, subnet_descriptions))
        for subnet_for_vpc in subnets_for_vpc:
            agent.relation(subnet_for_vpc['SubnetId'], vpc_id, 'uses service', {})

    # Create all subnet components
    for subnet_description_raw in subnet_descriptions:
        subnet_description = make_valid_data(subnet_description_raw)
        subnet_id = subnet_description['SubnetId']
        subnet_description.update(location_info)
        subnet_description['URN'] = [
            create_resource_arn(
                'ec2',
                location_info['Location']['AwsRegion'],
                location_info['Location']['AwsAccount'],
                'subnet',
                subnet_id
            )
        ]
        agent.component(subnet_id, 'aws.subnet', subnet_description)
