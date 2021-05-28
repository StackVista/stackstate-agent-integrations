from .utils import make_valid_data, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType


class RedshiftEventBase(CloudTrailEventBase):
    def get_collector_class(self):
        return RedshiftCollector

    def _internal_process(self, session, location, agent):
        if self.get_operation_type() == 'D':
            agent.delete(self.get_resource_arn(agent, location))
        else:
            client = session.client('redshift')
            collector = RedshiftCollector(location, client, agent)
            collector.process_one_cluster(self.get_resource_arn(agent, location))


class RedshiftEventUpdate(RedshiftEventBase):
    class RequestParameters(Model):
        clusterIdentifier = StringType()

    requestParameters = ModelType(RequestParameters)

    def get_resource_name(self):
        return self.requestParameters.clusterIdentifier

    def get_operation_type(self):
        return 'U' if self.eventName != 'DeleteCluster' else 'D'


class RedshiftEventCreate(RedshiftEventBase):
    class ResponseElements(Model):
        clusterIdentifier = StringType()

    responseElements = ModelType(ResponseElements)

    def get_resource_name(self):
        return self.responseElements.clusterIdentifier

    def get_operation_type(self):
        return 'C'


class RedshiftCollector(RegisteredResourceCollector):
    API = "redshift"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.redshift"
    EVENT_SOURCE = "redshift.amazonaws.com"
    CLOUDTRAIL_EVENTS = {
        'CreateCluster': RedshiftEventCreate,
        'DeleteCluster': RedshiftEventUpdate
    }
    CLOUDFORMATION_TYPE = "AWS::Redshift::Cluster"

    def process_all(self, filter=None):
        for page in self.client.get_paginator('describe_clusters').paginate():
            for redshift_data_raw in page.get('Clusters') or []:
                redshift_data = make_valid_data(redshift_data_raw)
                self.process_redshift(redshift_data)

    def process_one_cluster(self, clusterid):
        for page in self.client.get_paginator('describe_clusters').paginate(ClusterIdentifier=clusterid):
            for redshift_data_raw in page.get('Clusters') or []:
                redshift_data = make_valid_data(redshift_data_raw)
                self.process_redshift(redshift_data)

    def process_redshift(self, redshift_data):
        self.emit_component(redshift_data['ClusterIdentifier'], self.COMPONENT_TYPE, redshift_data)
        vpcid = redshift_data.get('VpcId')
        if vpcid:
            self.emit_relation(redshift_data['ClusterIdentifier'], vpcid, 'uses service', {})
