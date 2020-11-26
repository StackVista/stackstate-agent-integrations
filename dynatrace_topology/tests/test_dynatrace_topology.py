# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import unittest
import json
import requests_mock
from six import PY3

from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
from stackstate_checks.base.stubs import topology, aggregator


def _read_data(filename):
    with open("./tests/samples/" + filename, "r") as f:
        return json.load(f)


def _read_test_file(filename):
    with open("./tests/samples/" + filename, "r") as f:
        return f.read() if PY3 else f.read().decode("utf-8")


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

    @staticmethod
    def _set_http_responses(m, hosts="[]", apps="[]", svcs="[]", procs="[]", proc_groups="[]"):
        m.get("/api/v1/entity/infrastructure/hosts", text=hosts)
        m.get("/api/v1/entity/applications", text=apps)
        m.get("/api/v1/entity/services", text=svcs)
        m.get("/api/v1/entity/infrastructure/processes", text=procs)
        m.get("/api/v1/entity/infrastructure/process-groups", text=proc_groups)

    @requests_mock.Mocker()
    def test_collect_empty_topology(self, m):
        """
        Testing Dynatrace check should not produce any topology
        """
        self._set_http_responses(m)

        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 0)

    @requests_mock.Mocker()
    def test_collect_processes(self, m):
        """
        Testing Dynatrace check should collect processes
        """
        self._set_http_responses(m, procs=_read_test_file("process_response.json"))

        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = _read_data("process_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    @requests_mock.Mocker()
    def test_collect_hosts(self, m):
        """
        Testing Dynatrace check should collect hosts
        """
        self._set_http_responses(m, hosts=_read_test_file("host_response.json"))

        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = _read_data("host_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    @requests_mock.Mocker()
    def test_collect_services(self, m):
        """
        Testing Dynatrace check should collect services and tags coming from Kubernetes
        """
        self._set_http_responses(m, svcs=_read_test_file("service_response.json"))

        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = _read_data("service_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    @requests_mock.Mocker()
    def test_collect_applications(self, m):
        """
        Testing Dynatrace check should collect applications and also the tags properly coming from dynatrace
        """
        self._set_http_responses(m, apps=_read_test_file("application_response.json"))

        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = _read_data("application_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    @requests_mock.Mocker()
    def test_collect_process_groups(self, m):
        """
        Testing Dynatrace check should collect process-groups
        """
        self._set_http_responses(m, proc_groups=_read_test_file("process-group_response.json"))

        self.check.url = self.instance.get('url')

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = _read_data("process-group_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        actual_components, actual_relations = sort_topology_data(actual_topology)

        self.assertEqual(components, actual_components)
        self.assertEqual(len(relations), len(actual_relations))
        for relation in relations:
            self.assertIn(relation, actual_relations)

    def test_collect_relations(self):
        """
        Test to check if relations are collected properly
        """
        component = _read_data("host_response.json")[0]
        self.check.collect_relations(component, component.get('entityId'))

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 3)

        # since all relations are to this host itself so target id is same
        relation = topo_instances['relations'][0]
        self.assertEqual(relation['target_id'], component.get('entityId'))
        self.assertIn(relation['type'], ['isProcessOf', 'runsOn', 'isSiteOf'])

    @requests_mock.Mocker()
    def test_check_raise_exception(self, m):
        """
        Test to raise a check exception when collecting components and snapshot should be False
        """
        m.get("/api/v1/entity", exc=Exception("Exception occured"))

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

    @requests_mock.Mocker()
    def test_full_topology(self, m):
        """
        Test e2e to collect full topology for all component types from Dynatrace
        :return:
        """
        self._set_http_responses(m,
                                 hosts=_read_test_file("host_response.json"),
                                 apps=_read_test_file("application_response.json"),
                                 svcs=_read_test_file("service_response.json"),
                                 procs=_read_test_file("process_response.json"),
                                 proc_groups=_read_test_file("process-group_response.json")
                                 )

        self.check.url = self.instance.get('url')
        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        expected_topology = _read_data("smartscape_full_response_topology.json")

        # sort the keys of components and relations, so we match it in actual
        components, relations = sort_topology_data(topo_instances)
        expected_components, expected_relations = sort_topology_data(expected_topology)

        self.assertEqual(len(components), len(expected_components))
        for component in components:
            self.assertIn(component, expected_components)

        # Not comparing the numbers because we have duplicate relations created but
        # duplicates will be filtered out by the agent externalId assigning behavior
        for relation in relations:
            self.assertIn(relation, expected_relations)
