# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# 3p
import unittest

import pytest

# project
from stackstate_checks.agent_v2_integration_stateful_sample import AgentIntegrationSampleStatefulCheck
from stackstate_checks.base.stubs import topology, aggregator, telemetry, health, state
from stackstate_checks.base.utils.common import load_json_from_file


class InstanceInfo:
    def __init__(self, instance_tags):
        self.instance_tags = instance_tags


instance = {}

CONFIG = {
    'init_config': {'default_timeout': 10},
    'instances': [{'collection_interval': 5}]
}


@pytest.mark.usefixtures("instance")
class TestStatefulAgentV2Integration(unittest.TestCase):
    """Basic Test for Agent V2 integration."""
    CHECK_NAME = 'agent-v2-integration-stateful-sample'

    @staticmethod
    def reset_without_transaction_and_state():
        topology.reset()
        aggregator.reset()
        health.reset()
        telemetry.reset()

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        config = {}
        self.check = AgentIntegrationSampleStatefulCheck(self.CHECK_NAME, config, instances=[self.instance])
        self.reset_without_transaction_and_state()
        state.reset()

    def test_check(self):
        result = self.check.run()
        assert result == ''
        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 7)
        self.assertEqual(len(topo_instances['relations']), 3)

        assert topo_instances == load_json_from_file('expected_topology_instance.json', 'expected')

        aggregator.assert_metric('system.cpu.usage', count=3, tags=["hostname:this-host", "region:eu-west-1"])
        aggregator.assert_metric('location.availability', count=3, tags=["hostname:this-host", "region:eu-west-1"])
        aggregator.assert_metric('2xx.responses', count=4, tags=["application:some_application", "region:eu-west-1"])
        aggregator.assert_metric('5xx.responses', count=4, tags=["application:some_application", "region:eu-west-1"])
        aggregator.assert_metric('check_runs', count=1, tags=["integration:agent_v2_integration_stateful_sample"])
        aggregator.assert_event('Http request to {} timed out after {} seconds.'.format('http://localhost', 5.0),
                                count=1)
        telemetry.assert_topology_event(
            {
                "timestamp": int(1),
                "event_type": "HTTP_TIMEOUT",
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
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 30},
                               stop_snapshot={},
                               check_states=[{'checkStateId': 'id',
                                              'health': 'CRITICAL',
                                              'name': 'name',
                                              'topologyElementIdentifier': 'identifier',
                                              'message': 'msg'}
                                             ])

        telemetry.assert_metric("raw.metrics", count=2, value=20,
                                tags=["application:some_application", "region:eu-west-1"],
                                hostname="hostname")
        telemetry.assert_metric("raw.metrics", count=1, value=30, tags=["no:hostname", "region:eu-west-1"],
                                hostname="")

        # Testing for persistent state after the 1st check execution
        state.assert_state(self.check, expected_key="persistent_counter", expected_value=1)

        # Run the check for a second time to test persistent state
        self.check.run()

        # Testing for a persistent state after the 2nd check execution
        # Expecting the previous value set after the 1st execution to increase
        state.assert_state(self.check, expected_key="persistent_counter", expected_value=2)

    def test_topology_items_from_config_check(self):
        instance_config = {
            "stackstate-layer": "layer-conf-a",
            "stackstate-environment": "environment-conf-a",
            "stackstate-domain": "domain-conf-a",
            "collection_interval": 5
        }
        self.check = AgentIntegrationSampleStatefulCheck(self.CHECK_NAME, {}, instances=[instance_config])
        result = self.check.run()
        assert result == ''
        topo_instances = topology.get_snapshot(self.check.check_id)

        assert topo_instances == load_json_from_file('expected_topology_instance_topology_config.json', 'expected')
