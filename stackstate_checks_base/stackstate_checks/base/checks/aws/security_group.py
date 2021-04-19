from .utils import make_valid_data, create_resource_arn, create_hash
from .registry import RegisteredResourceCollector


class SecurityGroup_Collector(RegisteredResourceCollector):
    API = "ec2"
    COMPONENT_TYPE = "aws.security-group"

    def process_all(self):
        groups = {}
        for group_data_raw in self.client.describe_security_groups().get('SecurityGroups') or []:
            group_data = make_valid_data(group_data_raw)
            result = self.process_security_group(group_data)
            groups.update(result)
        if len(groups.keys()) > 0:
            return {'groups': groups}
        else:
            return None

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

        self.agent.component(group_id, self.COMPONENT_TYPE, group_data)

        if group_data.get('VpcId'):
            self.agent.relation(group_data['VpcId'], group_id, 'has resource', {})
        return {group_id: group_id}
