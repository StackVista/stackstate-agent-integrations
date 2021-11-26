# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import requests
import sys
import yaml
from stackstate_checks.checks import AgentCheck
from stackstate_checks.base import AgentCheck, ConfigurationError, HealthStreamUrn, HealthStream, Health
from stackstate_checks.base.errors import CheckException
from schematics.exceptions import ValidationError

# 
# This version of the check only works for Prometheus running in Kubernetes clusters 
# that also run the StackState agent to gather topology data
#
class PrometheusHealthCheck(AgentCheck):
    SERVICE_CHECK_NAME = "prometheus.health_information"
    WORKLOAD_TYPES = [ 'statefulset', 'replicaset', 'deployment', 'cronjob']

    def get_health_stream(self, instance):
        if 'cluster_name' not in instance:
            raise ConfigurationError('Missing cluster_name instance configuration.')
        instance_identifier = instance['cluster_name']
        return HealthStream(
          urn=HealthStreamUrn("prometheus", instance_identifier),
          sub_stream="default",
          repeat_interval_seconds=30,
          expiry_seconds=120
        )

    def check(self, instance):
        if 'url' not in instance:
            raise ConfigurationError('Missing url in topology instance configuration.')
        prometheus_url = instance['url']
        self.health.start_snapshot()
        alert_endpoint = "{}/api/v1/alerts".format(prometheus_url)

        try:
            # TODO: Get the whole http setup from, for example, the opemetrics base check
            response = requests.get(alert_endpoint, headers=None, stream=True, timeout=10)
            
            try:
                response.raise_for_status()
                self.service_check(
                    self.SERVICE_CHECK_NAME,
                    AgentCheck.OK,
                    tags={}
                )
            except requests.HTTPError:
                response.close()
                self.service_check(
                    self.SERVICE_CHECK_NAME,
                    AgentCheck.CRITICAL,
                    tags={}
                )
                raise
            try:
                alerts = response.json()
                for alert in alerts['data']['alerts']:
                    if alert['state'] == 'firing':
                        labels = alert['labels']
                        topology_element_identifier = ""
                        for resource_type in self.WORKLOAD_TYPES:
                            if resource_type in labels:
                                topology_element_identifier = "urn:kubernetes:/{}:{}:{}/{}".format(instance['cluster_name'], labels['namespace'], resource_type, labels[resource_type])
                                break
                        if topology_element_identifier == "":
                            if 'container' in labels and 'pod' in labels:
                                topology_element_identifier = "urn:kubernetes:/{}:{}:pod/{}:container/{}".format(instance['cluster_name'], labels['namespace'], labels['pod'], labels['container'])
                            elif 'pod' in labels:
                                topology_element_identifier = "urn:kubernetes:/{}:{}:pod/{}".format(instance['cluster_name'], labels['namespace'], labels['pod'])
                            elif 'job_name' in labels:
                                topology_element_identifier = "urn:kubernetes:/{}:{}:job/{}".format(instance['cluster_name'], labels['namespace'], labels['job_name'])

                        if topology_element_identifier != "":
                            # TODO: Can we do some templating in the configuration file to customize the message?
                            # the opensource rules have standardized on a summary, description and runbook_url annotation which we could also 
                            # use as the default template
                            annotations = alert['annotations']
                            message = "## Annotations\n"
                            for key in annotations:
                                if annotations[key].startswith('http://') or annotations[key].startswith('https://'):
                                    message = message + "**[{}]({})**\n\n".format(key, annotations[key])
                                else:
                                    message = message + "**{}:**\n{}\n\n".format(key, annotations[key])

                            message = message + "\n## Labels\n"
                            for key in labels:
                                message = message + "**{}:**\n{}\n\n".format(key, labels[key])
                            check_id = "{}:{}".format(labels['alertname'], topology_element_identifier)
                            self.health.check_state(check_id, labels['alertname'], Health.CRITICAL, topology_element_identifier, message)
            except Exception as e:
                self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags={}, message=str(e))
                self.log.exception("Prometheus health exception: %s" % str(e))
                raise CheckException("Prometheus health failed with message: %s" % e, None, sys.exc_info()[2])
            finally: 
                response.close()
            self.health.stop_snapshot()
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags={}, message=str(e))
            self.log.exception("Prometheus health exception: %s" % str(e))
            raise CheckException("Prometheus health failed with message: %s" % e, None, sys.exc_info()[2])
