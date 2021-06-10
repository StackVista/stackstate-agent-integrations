from .utils import make_valid_data
from .registry import RegisteredResourceCollector


class RedshiftCollector(RegisteredResourceCollector):
    API = "redshift"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.redshift"
    CLOUDFORMATION_TYPE = "AWS::Redshift::Cluster"

    def process_all(self, filter=None):
        for page in self.client.get_paginator("describe_clusters").paginate():
            for redshift_data_raw in page.get("Clusters") or []:
                redshift_data = make_valid_data(redshift_data_raw)
                self.process_redshift(redshift_data)

    def process_one_cluster(self, clusterid):
        for page in self.client.get_paginator("describe_clusters").paginate(ClusterIdentifier=clusterid):
            for redshift_data_raw in page.get("Clusters") or []:
                redshift_data = make_valid_data(redshift_data_raw)
                self.process_redshift(redshift_data)

    def process_redshift(self, redshift_data):
        self.emit_component(redshift_data["ClusterIdentifier"], self.COMPONENT_TYPE, redshift_data)
        vpcid = redshift_data.get("VpcId")
        if vpcid:  # pragma: no cover
            self.emit_relation(redshift_data["ClusterIdentifier"], vpcid, "uses service", {})

    EVENT_SOURCE = "redshift.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateCluster", "path": "responseElements.clusterIdentifier", "processor": process_one_cluster},
        {
            "event_name": "DeleteCluster",
            "path": "requestParameters.clusterIdentifier",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
    ]
