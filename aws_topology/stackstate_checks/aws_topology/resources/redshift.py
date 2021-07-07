from .utils import (
    make_valid_data,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType


def create_cluster_arn(region=None, account_id=None, resource_id=None):
    return arn(resource="redshift", region=region, account_id=account_id, resource_id="cluster:" + resource_id)


class Cluster(Model):
    ClusterIdentifier = StringType(required=True)
    VpcId = StringType()


class RedshiftCollector(RegisteredResourceCollector):
    API = "redshift"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.redshift"
    CLOUDFORMATION_TYPE = "AWS::Redshift::Cluster"

    def collect_clusters(self, **kwargs):
        for cluster in client_array_operation(self.client, "describe_clusters", "Clusters", **kwargs):
            yield cluster

    @set_required_access_v2("redshift:DescribeClusters")
    def process_clusters(self):
        for cluster_data in self.collect_clusters():
            self.process_cluster(cluster_data)

    def process_all(self, filter=None):
        if not filter or "clusters" in filter:
            self.process_clusters()

    @set_required_access_v2("redshift:DescribeClusters")
    def process_one_cluster(self, cluster_id):
        for cluster_data in self.collect_clusters(ClusterIdentifier=cluster_id):
            self.process_cluster(cluster_data)

    @transformation()
    def process_cluster(self, data):
        cluster = Cluster(data, strict=False)
        cluster.validate()
        cluster_arn = self.agent.create_arn("AWS::Redshift::Cluster", self.location_info, cluster.ClusterIdentifier)
        output = make_valid_data(data)
        output["Name"] = cluster.ClusterIdentifier
        output["URN"] = [cluster_arn]
        self.emit_component(cluster_arn, "cluster", output)
        if cluster.VpcId:
            self.emit_relation(cluster_arn, cluster.VpcId, "uses-service", {})

    EVENT_SOURCE = "redshift.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateCluster", "path": "responseElements.clusterIdentifier", "processor": process_one_cluster},
        {
            "event_name": "DeleteCluster",
            "path": "requestParameters.clusterIdentifier",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
    ]
