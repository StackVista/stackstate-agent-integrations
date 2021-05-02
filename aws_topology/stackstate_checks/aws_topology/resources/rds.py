from .utils import make_valid_data, with_dimensions
from .registry import RegisteredResourceCollector


class RdsCollector(RegisteredResourceCollector):
    API = "rds"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.rds_cluster"

    def process_all(self, filter=None):
        rds = {}
        for instance_data_raw in self.client.describe_db_instances().get('DBInstances') or []:
            instance_data = make_valid_data(instance_data_raw)
            result = self.process_instance(instance_data)
            rds.update(result)

        for cluster_data_raw in self.client.describe_db_clusters().get('DBClusters') or []:
            cluster_data = make_valid_data(cluster_data_raw)
            self.process_cluster(cluster_data, rds)

        return rds

    def process_instance(self, instance_data):
        instance_arn = instance_data['DBInstanceArn']
        instance_id = instance_data['DBInstanceIdentifier']
        tags = self.client.list_tags_for_resource(ResourceName=instance_arn).get('TagList') or []
        instance_data['Tags'] = tags
        instance_data['URN'] = [
            "urn:endpoint:/%s" % instance_data['Endpoint']['Address']
        ]
        instance_data['Name'] = instance_id
        instance_data.update(with_dimensions([{'key': 'DBInstanceIdentifier', 'value': instance_id}]))
        self.agent.component(instance_arn, 'aws.rds_instance', instance_data)
        vpc_id = instance_data['DBSubnetGroup']['VpcId']
        self.agent.relation(instance_arn, vpc_id, 'uses service', {})
        if instance_data.get('VpcSecurityGroups'):  # TODO agent.create_security_group_relations (but needs change?)
            for security_group in instance_data['VpcSecurityGroups']:
                self.agent.relation(instance_arn, security_group['VpcSecurityGroupId'], 'uses service', {})
        return {instance_id: instance_arn}

    def process_cluster(self, cluster_data, db_instance_map):
        cluster_id = cluster_data['DBClusterIdentifier']
        cluster_arn = cluster_data['DBClusterArn']
        cluster_data['Name'] = cluster_arn
        cluster_data.update(with_dimensions([{'key': 'DBClusterIdentifier', 'value': cluster_id}]))
        self.agent.component(cluster_arn, self.COMPONENT_TYPE, cluster_data)
        for cluster_member in cluster_data['DBClusterMembers']:
            db_identifier = cluster_member['DBInstanceIdentifier']
            if db_instance_map[db_identifier]:
                self.agent.relation(cluster_arn, db_instance_map[db_identifier], 'has_cluster_node', {})
