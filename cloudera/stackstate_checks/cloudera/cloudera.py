# (C) Datadog, Inc. 2018
# (C) Datadog, Inc. Patrick Galbraith <patg@patg.net> 2013
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)

import cm_client
from cm_client.rest import ApiException

from stackstate_checks.base import AgentCheck, is_affirmative, TopologyInstance


class Cloudera(AgentCheck):
    SERVICE_CHECK_NAME = 'cloudera.can_connect'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)

    def check(self, instance):
        host, port, user, password, api_version, verify_ssl =  self._get_config(instance)

        if not host:
            raise Exception("Cloudera host name is required.")
        if not user:
            raise Exception("Cloudera Manager user name is required.")

        # Configure HTTP basic authorization: basic
        cm_client.configuration.username = user
        cm_client.configuration.password = password
        if verify_ssl:
            cm_client.configuration.verify_ssl = True

        # Construct base URL for API
        api_url = host + ':' + str(port) + '/api/' + api_version

        try:
            api_client = cm_client.ApiClient(api_url)

            # collect topology
            self._collect_topology(api_client)

        except ApiException as e:
            self.log.exception("An ApiException occured:- {}".format(str(e)))
            raise e
        except Exception as e:
            self.log.exception("error!")
            raise e

    def _get_config(self, instance):
        self.host = instance.get('host', '')
        self.port = int(instance.get('port', 0))
        self.api_version = instance.get('api_version', '')

        user = instance.get('username', '')
        password = str(instance.get('password', ''))
        verify_ssl = instance.get('verify_ssl', False)
        return self.host, self.port, user, password, self.api_version, verify_ssl

    def _collect_components(self, api_client):
        # collect cluster component and relations
        self._collect_cluster(api_client)
        # collect hosts component
        # self._collect_hosts(api_client)
        # collect services component
        # self._collect_services(api_client)
        # collect roles component
        # self._collect_roles(api_client)

    def _collect_cluster(self, api_client):
        try:
            # List all known clusters.
            cluster_api_instance = cm_client.ClustersResourceApi(api_client)
            cluster_api_response = cluster_api_instance.read_clusters(view='summary')
            for cluster_data in cluster_api_response.items:
                self.component(cluster_data.name, "cluster", cluster_data)
                # List all hosts and make relation with cluster
                hosts_api_response = cluster_api_instance.list_hosts(cluster_data.name)
                for host_data in hosts_api_response.items:
                    self.component(host_data.host_id, 'host', host_data)
                    self.relation(host_data.host_id, cluster_data.name, "hosts", {})
        except ApiException as e:
            print("Exception when calling ClustersResourceApi->read_clusters: %s\n" % e)
