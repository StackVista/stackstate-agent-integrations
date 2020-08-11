# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# 3p
import unittest
import pytest

# project
from stackstate_checks.agent_integration_sample import AgentIntegrationSampleCheck
from stackstate_checks.base.stubs import topology, aggregator


class InstanceInfo():
    def __init__(self, instance_tags):
        self.instance_tags = instance_tags


instance = {}

CONFIG = {
    'init_config': {'default_timeout': 10, 'min_collection_interval': 5},
    'instances': [{}]
}

instance_config = InstanceInfo([])


@pytest.mark.usefixtures("instance")
class TestAgentIntegration(unittest.TestCase):
    """Basic Test for servicenow integration."""
    CHECK_NAME = 'servicenow'

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        config = {}
        self.check = AgentIntegrationSampleCheck(self.CHECK_NAME, config, instances=[self.instance])

    def test_check(self):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 5)
        self.assertEqual(len(topo_instances['relations']), 3)

        assert topo_instances == {
          'components': [
            {
              'data': {
                'cluster': 'stubbed-cluster-name',
                'hostname': 'stubbed.hostname',
                'identifiers': [
                  'urn:process:/stubbed.hostname:1:1234567890'
                ],
                'name': 'StackState Agent:stubbed.hostname',
                'tags': sorted([
                  'hostname:stubbed.hostname',
                  'stackstate-agent',
                ])
              },
              'id': 'urn:stackstate-agent:/stubbed.hostname',
              'type': 'stackstate-agent'
            },
            {
              'data': {
                'checks': [
                  {
                    'is_service_check_health_check': True,
                    'name': 'Integration Health',
                    'stream_id': -1
                  }
                ],
                'cluster': 'stubbed-cluster-name',
                'service_checks': [
                  {
                    'conditions': [
                      {
                        'key': 'host',
                        'value': 'stubbed.hostname'
                      },
                      {
                        'key': 'tags.integration-type',
                        'value': 'agent-integration'
                      }
                    ],
                    'identifier': topo_instances['components'][1]['data']['service_checks'][0]['identifier'],
                    'name': 'Service Checks',
                    'stream_id': -1
                  }
                ],
                'hostname': 'stubbed.hostname',
                'integration': 'agent-integration',
                'name': 'stubbed.hostname:agent-integration',
                'tags': sorted([
                  'hostname:stubbed.hostname',
                  'integration-type:agent-integration',
                ])
              },
              'id': 'urn:agent-integration:/stubbed.hostname:agent-integration',
              'type': 'agent-integration'
            },
            {
              'data': {
                'checks': [
                  {
                    'is_service_check_health_check': True,
                    'name': 'Integration Instance Health',
                    'stream_id': -1
                  }
                ],
                'cluster': 'stubbed-cluster-name',
                'service_checks': [
                  {
                    'conditions': [
                      {
                        'key': 'host',
                        'value': 'stubbed.hostname'
                      },
                      {
                        'key': 'tags.integration-type',
                        'value': 'agent-integration'
                      },
                      {
                        'key': 'tags.integration-url',
                        'value': 'sample'
                      }
                    ],
                    'identifier': topo_instances['components'][2]['data']['service_checks'][0]['identifier'],
                    'name': 'Service Checks',
                    'stream_id': -1
                  }
                ],
                'hostname': 'stubbed.hostname',
                'integration': 'agent-integration',
                'name': 'agent-integration:sample',
                'tags': sorted([
                  'hostname:stubbed.hostname',
                  'integration-type:agent-integration',
                  'integration-url:sample'
                ])
              },
              'id': 'urn:agent-integration-instance:/stubbed.hostname:agent-integration:sample',
              'type': 'agent-integration-instance'
            },
            {
              'data': {
                'checks': [
                  {
                    'critical_value': 90,
                    'deviating_value': 75,
                    'is_metric_maximum_average_check': True,
                    'max_window': 300000,
                    'name': 'Max CPU Usage (Average)',
                    'remediation_hint': 'There is too much activity on this host',
                    'stream_id': -1
                  },
                  {
                    'critical_value': 90,
                    'deviating_value': 75,
                    'is_metric_maximum_last_check': True,
                    'max_window': 300000,
                    'name': 'Max CPU Usage (Last)',
                    'remediation_hint': 'There is too much activity on this host',
                    'stream_id': -1
                  },
                  {
                    'critical_value': 5,
                    'deviating_value': 10,
                    'is_metric_minimum_average_check': True,
                    'max_window': 300000,
                    'name': 'Min CPU Usage (Average)',
                    'remediation_hint': 'There is too few activity on this host',
                    'stream_id': -1
                  },
                  {
                    'critical_value': 5,
                    'deviating_value': 10,
                    'is_metric_minimum_last_check': True,
                    'max_window': 300000,
                    'name': 'Min CPU Usage (Last)',
                    'remediation_hint': 'There is too few activity on this host',
                    'stream_id': -1
                  }
                ],
                'domain': 'Webshop',
                'environment': 'Production',
                'identifiers': [
                  'another_identifier_for_this_host'
                ],
                'labels': [
                  'host:this_host',
                  'region:eu-west-1'
                ],
                'tags': sorted([
                  'integration-type:agent-integration',
                  'integration-url:sample'
                ]),
                'layer': 'Machines',
                'metrics': [
                  {
                    'aggregation': 'MEAN',
                    'conditions': [
                      {
                        'key': 'tags.hostname',
                        'value': 'this-host'
                      },
                      {
                        'key': 'tags.region',
                        'value': 'eu-west-1'
                      }
                    ],
                    'identifier': topo_instances['components'][3]['data']['metrics'][0]['identifier'],
                    'metric_field': 'system.cpu.usage',
                    'name': 'Host CPU Usage',
                    'priority': 'HIGH',
                    'stream_id': -1,
                    'unit_of_measure': 'Percentage'
                  },
                  {
                    'aggregation': 'MEAN',
                    'conditions': [
                      {
                        'key': 'tags.hostname',
                        'value': 'this-host'
                      },
                      {
                        'key': 'tags.region',
                        'value': 'eu-west-1'
                      }
                    ],
                    'identifier': topo_instances['components'][3]['data']['metrics'][1]['identifier'],
                    'metric_field': 'location.availability',
                    'name': 'Host Availability',
                    'priority': 'HIGH',
                    'stream_id': -2,
                    'unit_of_measure': 'Percentage'
                  }
                ],
                'name': 'this-host'
              },
              'id': 'urn:example:/host:this_host',
              'type': 'Host'
            },
            {
              'data': {
                'checks': [
                  {
                    'critical_value': 75,
                    'denominator_stream_id': -1,
                    'deviating_value': 50,
                    'is_metric_maximum_ratio_check': True,
                    'max_window': 300000,
                    'name': 'OK vs Error Responses (Maximum)',
                    'numerator_stream_id': -2
                  },
                  {
                    'critical_value': 70,
                    'deviating_value': 50,
                    'is_metric_maximum_percentile_check': True,
                    'max_window': 300000,
                    'name': 'Error Response 99th Percentile',
                    'percentile': 99,
                    'stream_id': -2
                  },
                  {
                    'critical_value': 75,
                    'denominator_stream_id': -1,
                    'deviating_value': 50,
                    'is_metric_failed_ratio_check': True,
                    'max_window': 300000,
                    'name': 'OK vs Error Responses (Failed)',
                    'numerator_stream_id': -2
                  },
                  {
                    'critical_value': 5,
                    'deviating_value': 10,
                    'is_metric_minimum_percentile_check': True,
                    'max_window': 300000,
                    'name': 'Success Response 99th Percentile',
                    'percentile': 99,
                    'stream_id': -1
                  }
                ],
                'domain': 'Webshop',
                'environment': 'Production',
                'identifiers': [
                  'another_identifier_for_some_application'
                ],
                'labels': [
                  'application:some_application',
                  'region:eu-west-1',
                  'hosted_on:this-host'
                ],
                'tags': sorted([
                  'integration-type:agent-integration',
                  'integration-url:sample'
                ]),
                'layer': 'Applications',
                'metrics': [
                  {
                    'aggregation': 'MEAN',
                    'conditions': [
                      {
                        'key': 'tags.application',
                        'value': 'some_application'
                      },
                      {
                        'key': 'tags.region',
                        'value': 'eu-west-1'
                      }
                    ],
                    'identifier': topo_instances['components'][4]['data']['metrics'][0]['identifier'],
                    'metric_field': '2xx.responses',
                    'name': '2xx Responses',
                    'priority': 'HIGH',
                    'stream_id': -1,
                    'unit_of_measure': 'Count'
                  },
                  {
                    'aggregation': 'MEAN',
                    'conditions': [
                      {
                        'key': 'tags.application',
                        'value': 'some_application'
                      },
                      {
                        'key': 'tags.region',
                        'value': 'eu-west-1'
                      }
                    ],
                    'identifier': topo_instances['components'][4]['data']['metrics'][1]['identifier'],
                    'metric_field': '5xx.responses',
                    'name': '5xx Responses',
                    'priority': 'HIGH',
                    'stream_id': -2,
                    'unit_of_measure': 'Count'
                  }
                ],
                'name': 'some-application',
                'version': '0.2.0'
              },
              'id': 'urn:example:/application:some_application',
              'type': 'Application'
            }
          ],
          'instance_key': {
            'type': 'agent',
            'url': 'integrations'
          },
          'relations': [
            {
              'data': {},
              'source_id': 'urn:stackstate-agent:/stubbed.hostname',
              'target_id': 'urn:agent-integration:/stubbed.hostname:agent-integration',
              'type': 'runs'
            },
            {
              'data': {},
              'source_id': 'urn:agent-integration:/stubbed.hostname:agent-integration',
              'target_id': 'urn:agent-integration-instance:/stubbed.hostname:agent-integration:sample',
              'type': 'has'
            },
            {
              'data': {},
              'source_id': 'urn:example:/application:some_application',
              'target_id': 'urn:example:/host:this_host',
              'type': 'IS_HOSTED_ON'
            }
          ],
          'start_snapshot': False,
          'stop_snapshot': False
        }

        aggregator.assert_metric('system.cpu.usage', count=3, tags=["hostname:this-host", "region:eu-west-1"])
        aggregator.assert_metric('location.availability', count=3, tags=["hostname:this-host", "region:eu-west-1"])
        aggregator.assert_metric('2xx.responses', count=4, tags=["application:some_application", "region:eu-west-1"])
        aggregator.assert_metric('5xx.responses', count=4, tags=["application:some_application", "region:eu-west-1"])
        aggregator.assert_event('Http request to {} timed out after {} seconds.'.format('http://localhost', 5.0),
                                count=1)
        aggregator.assert_service_check('example.can_connect', self.check.OK)
