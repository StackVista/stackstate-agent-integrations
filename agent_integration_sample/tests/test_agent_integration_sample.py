# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# 3p
import unittest
import pytest

# project
from stackstate_checks.agent_integration_sample import AgentIntegrationSampleCheck
from stackstate_checks.base.stubs import topology


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

        result = self.check.run()
        print(result)
        topo_instances = topology.get_snapshot(self.check.check_id)
        print(topo_instances)
        self.assertEqual(len(topo_instances['components']), 4)
        self.assertEqual(len(topo_instances['relations']), 2)
