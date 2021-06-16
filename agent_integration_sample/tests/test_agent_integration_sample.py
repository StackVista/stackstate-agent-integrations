# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# 3p
import unittest
import pytest
import json
import os

# project
from stackstate_checks.agent_integration_sample import AgentIntegrationSampleCheck
from stackstate_checks.base.stubs import topology, aggregator, telemetry


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
    CHECK_NAME = 'agent-integration-sample'

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        config = {}
        self.check = AgentIntegrationSampleCheck(self.CHECK_NAME, config, instances=[self.instance])

    def test_check(self):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        result = self.check.run()
        assert result == ''
        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 6)
        self.assertEqual(len(topo_instances['relations']), 3)

        assert topo_instances == self._read_data('expected_topology_instance.json')

        aggregator.assert_metric('system.cpu.usage', count=3, tags=["hostname:this-host", "region:eu-west-1"])
        aggregator.assert_metric('location.availability', count=3, tags=["hostname:this-host", "region:eu-west-1"])
        aggregator.assert_metric('2xx.responses', count=4, tags=["application:some_application", "region:eu-west-1"])
        aggregator.assert_metric('5xx.responses', count=4, tags=["application:some_application", "region:eu-west-1"])
        aggregator.assert_metric('check_runs', count=1, tags=["integration:agent_integration_sample"])
        aggregator.assert_event('Http request to {} timed out after {} seconds.'.format('http://localhost', 5.0),
                                count=1)
        telemetry.assert_topology_event(
          {
            "timestamp": int(1),
            "source_type_name": "HTTP_TIMEOUT",
            "msg_title": "URL timeout",
            "msg_text": "Http request to http://localhost timed out after 5.0 seconds.",
            "aggregation_key": "instance-request-http://localhost",
            "context": {
              "source_identifier": "source_identifier_value",
              "element_identifiers": ["urn:host:/123"],
              "source": "source_value",
              "category": "my_category",
              "data": {"big_black_hole": "here", "another_thing": 1, "test": {"1": "test"}},
              "source_links": [
                {"title": "my_event_external_link", "url": "http://localhost"}
              ]
            }
          },
          count=1
        )
        aggregator.assert_service_check('example.can_connect', self.check.OK)

    def test_topology_items_from_config_check(self):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        instance_config = {
           "stackstate-layer": "layer-conf-a",
           "stackstate-environment": "environment-conf-a",
           "stackstate-domain": "domain-conf-a"
        }
        self.check = AgentIntegrationSampleCheck(self.CHECK_NAME, {}, instances=[instance_config])
        result = self.check.run()
        assert result == ''
        topo_instances = topology.get_snapshot(self.check.check_id)

        assert topo_instances == self._read_data('expected_topology_instance_topology_config.json')

    @staticmethod
    def _read_data(filename):
        path_to_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'expected', filename)
        with open(path_to_file, "r") as f:
            return json.load(f)
