# (C) Datadog, Inc. 2018
# (C) Datadog, Inc. Patrick Galbraith <patg@patg.net> 2013
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)

import cm_client
from cm_client.rest import ApiException

try:
    from urlparse import urlparse
except ModuleNotFoundError:
    from urllib.parse import urlparse

from stackstate_checks.base import AgentCheck, is_affirmative, TopologyInstance, ConfigurationError


def dict_from_cls(cls):
    return dict((key, str(value)) for (key, value) in cls.__dict__.items())


class Cloudera(AgentCheck):
    SERVICE_CHECK_NAME = 'cloudera.can_connect'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)

    def get_instance_key(self, instance):
        if 'url' not in instance:
            raise ConfigurationError('Missing url in topology instance configuration.')

        instance_url = urlparse(instance['url']).netloc
        return TopologyInstance('Cloudera', instance_url)

    def check(self, instance):
        url, port, user, password, api_version, verify_ssl = self._get_config(instance)

        if not user:
            raise ConfigurationError('Cloudera Manager user name is required.')

        if not password:
            raise ConfigurationError('Cloudera Manager user password is required.')

        # Configure HTTP basic authorization: basic
        cm_client.configuration.username = user
        cm_client.configuration.password = password
        if verify_ssl:
            cm_client.configuration.verify_ssl = True

        # Construct base URL for API
        api_url = url + ':' + str(port) + '/api/' + api_version

        try:
            api_client = cm_client.ApiClient(api_url)

            # collect topology
            self.start_snapshot()
            self._collect_topology(api_client)
            self.stop_snapshot()

        except ApiException as e:
            self.log.exception('An ApiException occurred: {}'.format(str(e)))
            raise e
        except Exception as e:
            self.log.exception('error!')
            raise e

    def _collect_topology(self, api_client):
        self._collect_hosts(api_client)
        self._collect_cluster(api_client)

    def _collect_hosts(self, api_client):
        try:
            host_api_instance = cm_client.HostsResourceApi(api_client)
            host_api_response = host_api_instance.read_hosts(view='summary')
            for host_data in host_api_response.items:
                self.component(host_data.host_id, 'host', dict_from_cls(host_data))
        except ApiException as e:
            print('Exception when calling ClustersResourceApi->read_hosts: {}'.format(e))

    def _collect_cluster(self, api_client):
        try:
            cluster_api_instance = cm_client.ClustersResourceApi(api_client)
            cluster_api_response = cluster_api_instance.read_clusters(view='summary')
            for cluster_data in cluster_api_response.items:
                self.component(cluster_data.name, 'cluster', dict_from_cls(cluster_data))
                hosts_api_response = cluster_api_instance.list_hosts(cluster_data.name)
                for host_data in hosts_api_response.items:
                    self.relation(host_data.host_id, cluster_data.name, 'hosts', {})
                self._collect_services(api_client, cluster_data.name)
        except ApiException as e:
            print('Exception when calling ClustersResourceApi->read_clusters: {}'.format(e))

    def _collect_services(self, api_client, cluster_name):
        try:
            services_api_instance = cm_client.ServicesResourceApi(api_client)
            resp = services_api_instance.read_services(cluster_name, view='summary')
            for service_data in resp.items:
                self.component(service_data.name, 'service', dict_from_cls(service_data))
                self.relation(cluster_name, service_data.name, 'runs', {})
        except ApiException as e:
            print('Exception when calling ClustersResourceApi->read_clusters: {}'.format(e))

    def _collect_roles(self, api_client, cluster_name, service_name):
        roles_api_instance = cm_client.RolesResourceApi(api_client)
        roles_api_response = roles_api_instance.read_roles(cluster_name, service_name, view='summary')
        for role_data in roles_api_response.items:
            self.component(role_data.name, 'role', dict_from_cls(role_data))
            self.relation(service_name, role_data.name, 'has a', {})

    def _get_config(self, instance):
        self.url = instance.get('url', '')
        self.port = int(instance.get('port', 0))
        api_version = instance.get('api_version', '')
        user = instance.get('username', '')
        password = str(instance.get('password', ''))
        verify_ssl = is_affirmative(instance.get('verify_ssl'))
        return self.url, self.port, user, password, api_version, verify_ssl
