from .utils import make_valid_data, with_dimensions, create_arn as arn, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType


def create_cluster_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='rds', region=region, account_id=account_id, resource_id='cluster:' + resource_id)


def create_db_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='rds', region=region, account_id=account_id, resource_id='db:' + resource_id)


class Rds_ClusterEvent(CloudTrailEventBase):
    def get_collector_class(self):
        return RdsCollector

    class ResponseElements(Model):
        dBClusterArn = StringType(required=True)

    responseElements = ModelType(ResponseElements)

    def get_resource_name(self):
        part = self.responseElements.dBClusterArn.rsplit(':', 1)[-1]
        name = part.rsplit('/', 1)[-1]
        return name

    def get_resource_arn(self, agent, location):
        return agent.create_arn('AWS::RDS::DBCluster', location, self.get_resource_name())

    def get_operation_type(self):
        return 'U' if self.eventName != 'DeleteDBCluster' else 'D'

    def _internal_process(self, session, location, agent):
        if self.get_operation_type() == 'D':
            agent.delete(self.get_resource_arn(agent, location))
        else:
            client = session.client('rds')
            collector = RdsCollector(location, client, agent)
            collector.process_one_cluster(self.get_resource_name())


class Rds_InstanceEvent(CloudTrailEventBase):
    def get_collector_class(self):
        return RdsCollector

    class ResponseElements(Model):
        dBInstanceArn = StringType(required=True)

    responseElements = ModelType(ResponseElements)

    def get_resource_name(self):
        part = self.responseElements.dBInstanceArn.rsplit(':', 1)[-1]
        name = part.rsplit('/', 1)[-1]
        return name

    def get_resource_arn(self, agent, location):
        return agent.create_arn('AWS::RDS::DBInstance', location, self.get_resource_name())

    def get_operation_type(self):
        return 'U' if self.eventName != 'DeleteDBInstance' else 'D'

    def _internal_process(self, session, location, agent):
        if self.get_operation_type() == 'D':
            agent.delete(self.get_resource_arn(agent, location))
        else:
            client = session.client('rds')
            collector = RdsCollector(location, client, agent)
            collector.process_one_instance(self.get_resource_name())


#        'AWS::RDS::DBCluster': {
#            'C': {
#                'events': ['CreateDBCluster'],
#                'path': 'responseElements.dBClusterArn',
#                'param': 'use_name'
#            }
#            'D': ['DeleteDBCluster']
#            'U': ['UpdateDbCluster', 'bladieblah']
#        },
#        'AWS::RDS::DBInstance': {
#            '':
#        },


class RdsCollector(RegisteredResourceCollector):
    API = "rds"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.rds_cluster"
    EVENT_SOURCE = 'rds.amazonaws.com'
    CLOUDTRAIL_EVENTS = {
        'CreateDBInstance': Rds_InstanceEvent,
        'CreateDBCluster': Rds_ClusterEvent,
        'DeleteDBInstance': Rds_InstanceEvent,
        'DeleteDBCluster': Rds_ClusterEvent
    }

    def process_all(self, filter=None):
        for instance_data_raw in self.client.describe_db_instances().get('DBInstances') or []:
            instance_data = make_valid_data(instance_data_raw)
            self.process_instance(instance_data)

        for cluster_data_raw in self.client.describe_db_clusters().get('DBClusters') or []:
            cluster_data = make_valid_data(cluster_data_raw)
            self.process_cluster(cluster_data)

    def process_one_cluster(self, id):
        for cluster_data_raw in self.client.describe_db_clusters(DBClusterIdentifier=id).get('DBClusters') or []:
            cluster_data = make_valid_data(cluster_data_raw)
            self.process_cluster(cluster_data)

    def process_one_instance(self, id):
        for instance_data_raw in self.client.describe_db_instances(DBInstanceIdentifier=id).get('DBInstances') or []:
            instance_data = make_valid_data(instance_data_raw)
            self.process_instance(instance_data)

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
        self.emit_component(instance_arn, 'aws.rds_instance', instance_data)
        vpc_id = instance_data['DBSubnetGroup']['VpcId']
        self.emit_relation(instance_arn, vpc_id, 'uses service', {})
        if instance_data.get('VpcSecurityGroups'):  # TODO agent.create_security_group_relations (but needs change?)
            for security_group in instance_data['VpcSecurityGroups']:
                self.emit_relation(instance_arn, security_group['VpcSecurityGroupId'], 'uses service', {})

    def process_cluster(self, cluster_data):
        cluster_id = cluster_data['DBClusterIdentifier']
        cluster_arn = cluster_data['DBClusterArn']
        cluster_data['Name'] = cluster_arn
        cluster_data.update(with_dimensions([{'key': 'DBClusterIdentifier', 'value': cluster_id}]))
        self.emit_component(cluster_arn, self.COMPONENT_TYPE, cluster_data)
        for cluster_member in cluster_data['DBClusterMembers']:
            db_identifier = cluster_member['DBInstanceIdentifier']
            arn = self.agent.create_arn('AWS::Rds::Cluster', self.location_info, db_identifier)
            self.emit_relation(cluster_arn, arn, 'has_cluster_node', {})
