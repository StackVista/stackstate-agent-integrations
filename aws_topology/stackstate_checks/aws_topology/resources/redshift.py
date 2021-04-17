from .utils import make_valid_data
from .registry import RegisteredResourceCollector


class Redshift_Collector(RegisteredResourceCollector):
    API = "redshift"
    COMPONENT_TYPE = "aws.redshift"

    def process_all(self):
        for page in self.client.get_paginator('describe_clusters').paginate():
            for redshift_data_raw in page.get('Clusters') or []:
                redshift_data = make_valid_data(redshift_data_raw)
                self.process_redshift(redshift_data)

    def process_redshift(self, redshift_data):
        self.agent.component(redshift_data['ClusterIdentifier'], self.COMPONENT_TYPE, redshift_data)
        self.agent.relation(redshift_data['ClusterIdentifier'], redshift_data['VpcId'], 'uses service', {})
