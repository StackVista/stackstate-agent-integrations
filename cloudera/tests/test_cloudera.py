import os
import jsonpickle as jsonpickle

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from stackstate_checks.base.stubs import topology
from stackstate_checks.cloudera import ClouderaCheck

try:
    from urlparse import urlparse
except ModuleNotFoundError:
    from urllib.parse import urlparse


class MockClouderaClient:
    def __init__(self, instance):
        pass

    def get_cluster_api(self):
        return self.read_data(self.get_file('cluster_api_response.json'))

    def get_host_api(self):
        return self.read_data(self.get_file('host_api_response.json'))

    def get_service_api(self, cluster_name):
        return self.read_data(self.get_file('services_api_response_{}.json'.format(cluster_name)))

    def get_roles_api(self, cluster_name, service_name):
        return self.read_data(self.get_file('roles_api_response_{}_{}.json'.format(cluster_name, service_name)))

    @staticmethod
    def read_data(file_name):
        with open(file_name, 'r') as file:
            json_file = file.read()
        return jsonpickle.decode(json_file)

    @staticmethod
    def get_file(file_name):
        return os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', file_name)


@patch('stackstate_checks.cloudera.cloudera.ClouderaClient', MockClouderaClient)
def test_check_collect_cluster(aggregator, instance):
    check = ClouderaCheck('test', {}, {}, instances=[instance])

    check.check(instance)
    snapshot = topology.get_snapshot('')
    instance_url = urlparse(instance['url']).netloc
    assert snapshot['instance_key']['url'] == instance_url
    assert len(snapshot['components']) == 133
    assert len(snapshot['relations']) == 132

    aggregator.assert_all_metrics_covered()
