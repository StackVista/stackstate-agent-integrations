# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import unittest
import yaml
import mock

from stackstate_checks.dynatrace import DynatraceCheck
from stackstate_checks.base.stubs import topology, aggregator


def read_data(filename):
    with open("./tests/samples/" + filename, "r") as f:
        data = yaml.safe_load(f)
        return data


@pytest.mark.usefixtures("instance")
class TestDynatrace(unittest.TestCase):
    """Basic Test for Dynatrace integration."""
    CHECK_NAME = 'dynatrace'
    SERVICE_CHECK_NAME = "dynatrace"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        config = {}
        self.check = DynatraceCheck(self.CHECK_NAME, config, instances=[self.instance])

    def test_collect_empty_topology(self):
        """
        Testing Dynatrace check should not produce any topology
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = []
        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 0)

    def test_collect_processes(self):
        """
        Testing Dynatrace check should collect processes
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("process_response.json")
        self.check.url = self.instance.get('url')

        self.check.collect_processes()

        topo_instances = topology.get_snapshot(self.check.check_id)

        self.assertEqual(len(topo_instances['components']), 3)
        # check the first component data and should match
        component1 = topo_instances['components'][0]
        self.assertEqual(component1['id'], 'PROCESS_GROUP_INSTANCE-F25A8361C6742030')
        self.assertEqual(component1['type'], 'process')
        self.assertEqual(component1['data']['identifiers'], ['urn:process:/PROCESS_GROUP_INSTANCE-F25A8361C6742030'])
        self.assertEqual(component1['data']['entityId'], 'PROCESS_GROUP_INSTANCE-F25A8361C6742030')

        self.assertEqual(len(topo_instances['relations']), 9)
        # check the third relation data and should match
        # relation = topo_instances['relations'][3]
        # self.assertEqual(relation['type'], 'isProcessOf')
        # self.assertEqual(relation['source_id'], 'PROCESS_GROUP_INSTANCE-F25A8361C6742030')
        # self.assertEqual(relation['target_id'], 'HOST-6AAE0F78BCF2E0F4')

    def test_collect_hosts(self):
        """
        Testing Dynatrace check should collect hosts
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("host_response.json")
        self.check.url = self.instance.get('url')

        self.check.collect_hosts()

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 2)
        # check the second component data and should match
        component = topo_instances['components'][1]
        self.assertEqual(component['id'], 'HOST-AA6A5D81A0006807')
        self.assertEqual(component['type'], 'host')
        self.assertEqual(component['data']['identifiers'], ['urn:host:/SQL01.stackstate.lab'])
        self.assertEqual(component['data']['entityId'], 'HOST-AA6A5D81A0006807')

        self.assertEqual(len(topo_instances['relations']), 6)

    def test_collect_services(self):
        """
        Testing Dynatrace check should collect services
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("service_response.json")
        self.check.url = self.instance.get('url')

        self.check.collect_services()

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 3)
        # check the third component data and should match
        component = topo_instances['components'][2]
        self.assertEqual(component['id'], 'SERVICE-329B4CC95B522941')
        self.assertEqual(component['type'], 'service')
        self.assertEqual(component['data']['identifiers'], ['urn:service:/SERVICE-329B4CC95B522941'])
        self.assertEqual(component['data']['entityId'], 'SERVICE-329B4CC95B522941')

        self.assertEqual(len(topo_instances['relations']), 9)

    def test_collect_applications(self):
        """
        Testing Dynatrace check should collect applications
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("application_response.json")
        self.check.url = self.instance.get('url')

        self.check.collect_applications()

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 3)
        # check the first component data and should match
        component = topo_instances['components'][0]
        self.assertEqual(component['id'], 'APPLICATION-EA7C4B59F27D43EB')
        self.assertEqual(component['type'], 'application')
        self.assertEqual(component['data']['identifiers'], ['urn:application:/APPLICATION-EA7C4B59F27D43EB'])
        self.assertEqual(component['data']['entityId'], 'APPLICATION-EA7C4B59F27D43EB')
        self.assertEqual(component['data']['tags'][0], 'Mytag')
        self.assertEqual(component['data']['tags'][1], 'Test')
        self.assertEqual(len(topo_instances['relations']), 3)

    def test_collect_process_groups(self):
        """
        Testing Dynatrace check should collect process-groups
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("process-group_response.json")
        self.check.url = self.instance.get('url')

        self.check.collect_proccess_groups()

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 3)
        # check the second component data and should match
        component = topo_instances['components'][1]
        self.assertEqual(component['id'], 'PROCESS_GROUP-647A29F2E878C508')
        self.assertEqual(component['type'], 'process-group')
        self.assertEqual(component['data']['identifiers'], ['urn:process-group:/PROCESS_GROUP-647A29F2E878C508'])
        self.assertEqual(component['data']['entityId'], 'PROCESS_GROUP-647A29F2E878C508')
        self.assertEqual(component['data']['displayName'], 'Elasticsearch stackstate')
        self.assertEqual(len(topo_instances['relations']), 14)

    def test_filter_data(self):
        """
        Test to check if relationships are removed from data
        """
        data = read_data("host_response.json")[0]
        result = self.check.filter_data(data.copy())
        self.assertNotIn("fromRelationships", result)
        self.assertNotIn("toRelationships", result)
        self.assertNotEqual(data, result)

    def test_filter_data_without_from_to_relationships(self):
        """
        Test to check if data remains same as no relationships existed
        """
        data = read_data("host_response.json")[0]
        del data["fromRelationships"]
        del data["toRelationships"]
        result = self.check.filter_data(data.copy())
        self.assertEqual(data, result)

    def test_collect_relations(self):
        """
        Test to check if relations are collected properly
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        component = read_data("host_response.json")[0]
        self.check.collect_relations(component, component.get('entityId'))

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 4)

        # since all relations are to this host itself so target id is same
        relation = topo_instances['relations'][0]
        self.assertEqual(relation['target_id'], component.get('entityId'))
        self.assertIn(relation['type'], ['isProcessOf', 'runsOn', 'isSiteOf'])

    def test_check_raise_exception(self):
        """
        Test to raise a check exception when collecting components
        """

        # TODO this is needed because the aggregator retains data across tests
        aggregator.reset()

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.side_effect = Exception("Exception occured")

        self.assertRaises(Exception, self.check.check(self.instance))
        service_checks = aggregator.service_checks("dynatrace")
        self.assertEqual(len(service_checks), 1)
        self.assertEqual(service_checks[0].name, self.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)
