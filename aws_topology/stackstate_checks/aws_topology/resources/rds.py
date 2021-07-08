from .utils import (
    make_valid_data,
    create_arn as arn,
    client_array_operation,
    with_dimensions,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ListType, ModelType


def create_cluster_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="rds", region=region, account_id=account_id, resource_id="cluster:" + resource_id)


def create_db_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="rds", region=region, account_id=account_id, resource_id="db:" + resource_id)


class TagList(Model):
    Key = StringType(required=True)
    Value = StringType(required=True)


class ClusterMember(Model):
    DBInstanceIdentifier = StringType(required=True)


class Cluster(Model):
    DBClusterArn = StringType(required=True)
    DBClusterIdentifier = StringType(default="UNKNOWN")
    DBClusterMembers = ListType(ModelType(ClusterMember))
    TagList = ListType(ModelType(TagList), default=[])
    Endpoint = StringType()
    ReaderEndpoint = StringType()


class InstanceSubnetGroup(Model):
    VpcId = StringType(required=True)


class InstanceEndpoint(Model):
    Address = StringType(required=True)


class InstanceVpcSecurityGroup(Model):
    VpcSecurityGroupId = StringType(required=True)


class Instance(Model):
    DBInstanceArn = StringType(required=True)
    DBInstanceIdentifier = StringType(default="UNKNOWN")
    DBSubnetGroup = ModelType(InstanceSubnetGroup)
    Endpoint = ModelType(InstanceEndpoint)
    VpcSecurityGroups = ListType(ModelType(InstanceVpcSecurityGroup), default=[])
    TagList = ListType(ModelType(TagList), default=[])


class RdsCollector(RegisteredResourceCollector):
    API = "rds"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.rds"

    def collect_clusters(self, **kwargs):
        for cluster in client_array_operation(self.client, "describe_db_clusters", "DBClusters", **kwargs):
            yield cluster

    def collect_instances(self, **kwargs):
        for instance in client_array_operation(self.client, "describe_db_instances", "DBInstances", **kwargs):
            yield instance

    @set_required_access_v2("rds:DescribeDBClusters")
    def process_clusters(self):
        for cluster_data in self.collect_clusters():
            self.process_cluster(cluster_data)

    @set_required_access_v2("rds:DescribeDBInstances")
    def process_instances(self):
        for instance_data in self.collect_instances():
            self.process_instance(instance_data)

    def process_all(self, filter=None):
        if not filter or "clusters" in filter:
            self.process_clusters()
        if not filter or "instances" in filter:
            self.process_instances()

    @set_required_access_v2("rds:DescribeDBClusters")
    def process_one_cluster(self, cluster_arn):
        for cluster_data in self.collect_clusters(DBClusterIdentifier=cluster_arn):
            self.process_cluster(cluster_data)

    @set_required_access_v2("rds:DescribeDBInstances")
    def process_one_instance(self, instance_arn):
        for instance_data in self.collect_instances(DBInstanceIdentifier=instance_arn):
            self.process_instance(instance_data)

    @transformation()
    def process_instance(self, data):
        instance = Instance(data, strict=False)
        instance.validate()
        output = make_valid_data(data)
        instance_arn = instance.DBInstanceArn
        instance_id = instance.DBInstanceIdentifier
        output["Name"] = instance_id
        output["Tags"] = instance.TagList
        if instance.Endpoint:
            output["URN"] = ["urn:endpoint:/" + instance.Endpoint.Address]
        output.update(with_dimensions([{"key": "DBInstanceIdentifier", "value": instance_id}]))
        self.emit_component(instance_arn, "instance", output)
        self.emit_relation(instance_arn, instance.DBSubnetGroup.VpcId, "uses-service", {})
        # TODO agent.create_security_group_relations (but needs change?)
        for security_group in instance.VpcSecurityGroups:
            self.emit_relation(instance_arn, security_group.VpcSecurityGroupId, "uses-service", {})

    @transformation()
    def process_cluster(self, data):
        cluster = Cluster(data, strict=False)
        cluster.validate()
        output = make_valid_data(data)
        cluster_id = cluster.DBClusterIdentifier
        cluster_arn = cluster.DBClusterArn
        output["Name"] = cluster_arn
        output["Tags"] = cluster.TagList
        urns = []
        if cluster.Endpoint:
            urns.append("urn:endpoint:/" + cluster.Endpoint)
        if cluster.ReaderEndpoint:
            urns.append("urn:endpoint:/" + cluster.ReaderEndpoint)
        output["URN"] = urns
        output.update(with_dimensions([{"key": "DBClusterIdentifier", "value": cluster_id}]))
        self.emit_component(cluster_arn, "cluster", output)
        for cluster_member in output.get("DBClusterMembers", []):
            db_identifier = cluster_member.get("DBInstanceIdentifier", "UNKNOWN")
            arn = self.agent.create_arn("AWS::RDS::DBInstance", self.location_info, db_identifier)
            self.emit_relation(cluster_arn, arn, "has_cluster_node", {})

    EVENT_SOURCE = "rds.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateDBInstance", "path": "responseElements.dBInstanceArn", "processor": process_one_instance},
        {
            "event_name": "DeleteDBInstance",
            "path": "responseElements.dBInstanceArn",
            "processor": RegisteredResourceCollector.emit_deletion,
        },
        {"event_name": "CreateDBCluster", "path": "responseElements.dBClusterArn", "processor": process_one_cluster},
        {
            "event_name": "DeleteDBCluster",
            "path": "responseElements.dBClusterArn",
            "processor": RegisteredResourceCollector.emit_deletion,
        },
    ]
