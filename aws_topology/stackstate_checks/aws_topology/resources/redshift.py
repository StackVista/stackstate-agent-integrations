from .utils import (
    make_valid_data,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType


def create_cluster_arn(region=None, account_id=None, resource_id=None):
    return arn(resource="redshift", region=region, account_id=account_id, resource_id="cluster:" + resource_id)


ClusterData = namedtuple("ClusterData", ["cluster", "tags", "arn"])


class Cluster(Model):
    ClusterIdentifer = StringType(required=True)
    VpcId = StringType()


class RedshiftCollector(RegisteredResourceCollector):
    API = "redshift"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.redshift"
    CLOUDFORMATION_TYPE = "AWS::Redshift::Cluster"

    @set_required_access_v2("redshift:DescribeTags")
    def collect_tags(self, cluster_arn):
        return [
            tags
            for tags in client_array_operation(
                self.client, "describe_tags", "TaggedResources", ResourceName=cluster_arn, ResourceType="Cluster"
            )
        ]

    def collect_cluster(self, cluster_data):
        cluster_arn = self.agent.create_arn(
            "AWS::Redshift::Cluster", self.location_info, cluster_data.get("ClusterIdentifier", "UNKNOWN")
        )
        tags = self.collect_tags(cluster_arn) or []
        return ClusterData(cluster=cluster_data, tags=tags, arn=cluster_arn)

    def collect_clusters(self, **kwargs):
        for cluster in [
            self.collect_cluster(cluster_data)
            for cluster_data in client_array_operation(self.client, "describe_clusters", "Clusters", **kwargs)
        ]:
            yield cluster

    @set_required_access_v2("redshift:DescribeClusters")
    def process_clusters(self):
        for cluster_data in self.collect_clusters():
            self.process_cluster(cluster_data)

    def process_all(self, filter=None):
        if not filter or "clusters" in filter:
            self.process_clusters()

    def process_one_cluster(self, cluster_id):
        for cluster_data in self.collect_clusters(ClusterIdentifier=cluster_id):
            self.process_cluster(cluster_data)

    @transformation()
    def process_cluster(self, data):
        cluster = Cluster(data.cluster, strict=False)
        cluster.validate()
        output = make_valid_data(data.cluster)
        output["Name"] = cluster.ClusterIdentifer
        output["Tags"] = data.tags
        output["URN"] = [data.arn]
        self.emit_component(data.arn, self.COMPONENT_TYPE, output)
        if cluster.VpcId:
            self.emit_relation(data.arn, cluster.VpcId, "uses service", {})

    EVENT_SOURCE = "redshift.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateCluster", "path": "responseElements.clusterIdentifier", "processor": process_one_cluster},
        {
            "event_name": "DeleteCluster",
            "path": "requestParameters.clusterIdentifier",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
    ]
