# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import unittest
import yaml
import mock
import json

from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
from stackstate_checks.base.stubs import topology, aggregator


def read_data(filename):
    with open("./tests/samples/" + filename, "r") as f:
        data = yaml.safe_load(f)
        return data


def sort_topology_data(topo_instances):
    components = [json.dumps(component, sort_keys=True) for component in topo_instances["components"]]
    relations = [json.dumps(relation, sort_keys=True) for relation in topo_instances["relations"]]
    return components, relations


@pytest.mark.usefixtures("instance")
class TestDynatraceTopologyCheck(unittest.TestCase):
    """Basic Test for Dynatrace integration."""
    CHECK_NAME = 'dynatrace'
    SERVICE_CHECK_NAME = "dynatrace"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        config = {}
        self.check = DynatraceTopologyCheck(self.CHECK_NAME, config, instances=[self.instance])

        # this is needed because the topology retains data across tests
        topology.reset()

    def test_collect_empty_topology(self):
        """
        Testing Dynatrace check should not produce any topology
        """

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

        # mock other component type calls and return empty response
        self.check.collect_services = mock.MagicMock(return_value=[])
        self.check.collect_process_groups = mock.MagicMock(return_value=[])
        self.check.collect_applications = mock.MagicMock(return_value=[])
        self.check.collect_hosts = mock.MagicMock(return_value=[])

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("process_response.json")
        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = read_data("process_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    def test_collect_hosts(self):
        """
        Testing Dynatrace check should collect hosts
        """

        # mock other component type calls and return empty response
        self.check.collect_services = mock.MagicMock(return_value=[])
        self.check.collect_process_groups = mock.MagicMock(return_value=[])
        self.check.collect_applications = mock.MagicMock(return_value=[])
        self.check.collect_processes = mock.MagicMock(return_value=[])

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("host_response.json")
        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = read_data("host_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    def test_collect_services(self):
        """
        Testing Dynatrace check should collect services and tags coming from Kubernetes
        """

        # mock other component type calls and return empty response
        self.check.collect_hosts = mock.MagicMock(return_value=[])
        self.check.collect_process_groups = mock.MagicMock(return_value=[])
        self.check.collect_applications = mock.MagicMock(return_value=[])
        self.check.collect_processes = mock.MagicMock(return_value=[])

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("service_response.json")
        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = read_data("service_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    def test_collect_applications(self):
        """
        Testing Dynatrace check should collect applications and also the tags properly coming from dynatrace
        """

        # mock other component type calls and return empty response
        self.check.collect_hosts = mock.MagicMock(return_value=[])
        self.check.collect_process_groups = mock.MagicMock(return_value=[])
        self.check.collect_services = mock.MagicMock(return_value=[])
        self.check.collect_processes = mock.MagicMock(return_value=[])

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("application_response.json")
        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = read_data("application_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    def test_collect_process_groups(self):
        """
        Testing Dynatrace check should collect process-groups
        """

        # mock other component type calls and return empty response
        self.check.collect_hosts = mock.MagicMock(return_value=[])
        self.check.collect_applications = mock.MagicMock(return_value=[])
        self.check.collect_services = mock.MagicMock(return_value=[])
        self.check.collect_processes = mock.MagicMock(return_value=[])

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = read_data("process-group_response.json")
        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = read_data("process-group_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

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

        component = read_data("host_response.json")[0]
        self.check.collect_relations(component, component.get('entityId'))

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 3)

        # since all relations are to this host itself so target id is same
        relation = topo_instances['relations'][0]
        self.assertEqual(relation['target_id'], component.get('entityId'))
        self.assertIn(relation['type'], ['isProcessOf', 'runsOn', 'isSiteOf'])

    def test_check_raise_exception(self):
        """
        Test to raise a check exception when collecting components and snapshot should be False
        """

        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.side_effect = Exception("Exception occured")

        self.assertRaises(Exception, self.check.check(self.instance))
        # since the check raised exception, the topology snapshot is not completed
        topo_instance = topology.get_snapshot(self.check.check_id)
        self.assertEqual(topo_instance.get("start_snapshot"), True)
        self.assertEqual(topo_instance.get("stop_snapshot"), False)
        # Service Checks should be generated
        service_checks = aggregator.service_checks("dynatrace")
        self.assertEqual(len(service_checks), 1)
        self.assertEqual(service_checks[0].name, self.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)

    def test_full_topology(self):
        """
        Test e2e to collect full topology for all component types from Dynatrace
        :return:
        """

        self.check.collect_hosts = mock.MagicMock(return_value=read_data("host_response.json"))
        self.check.collect_applications = mock.MagicMock(return_value=read_data("application_response.json"))
        self.check.collect_services = mock.MagicMock(return_value=read_data("service_response.json"))
        self.check.collect_processes = mock.MagicMock(return_value=read_data("process_response.json"))
        self.check.collect_process_groups = mock.MagicMock(return_value=read_data("process-group_response.json"))

        self.check.url = self.instance.get('url')
        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = read_data("smartscape_full_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(len(components), len(actual_components))
        for component in components:
            self.assertIn(component, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)
