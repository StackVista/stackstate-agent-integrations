# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import unittest

import pytest
import requests_mock

from stackstate_checks.base.stubs import topology, aggregator
from stackstate_checks.base.utils.common import read_file, load_json_from_file

from stackstate_checks.dynatrace_topology.dynatrace_topology import DynatraceTopologyCheck


def sort_topology_data(topology_instance):
    components = [json.dumps(component, sort_keys=True) for component in topology_instance["components"]]
    relations = [json.dumps(relation, sort_keys=True) for relation in topology_instance["relations"]]
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
    def _set_http_responses(m, hosts="[]", apps="[]", svcs="[]", procs="[]", proc_groups="[]", dev='{"entities":[]}'):
        m.get("/api/v1/entity/infrastructure/hosts", text=hosts)
        m.get("/api/v1/entity/applications", text=apps)
        m.get("/api/v1/entity/services", text=svcs)
        m.get("/api/v1/entity/infrastructure/processes", text=procs)
        m.get("/api/v1/entity/infrastructure/process-groups", text=proc_groups)
        m.get("/api/v2/entities", text=dev)
        m.get("/api/v1/events", text="[]")

    @requests_mock.Mocker()
    def test_collect_empty_topology(self, m):
        """
        Testing Dynatrace check should not produce any topology
        """
        self._set_http_responses(m)
        self.check.url = self.instance.get('url')
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['components']), 0)
        self.assertEqual(len(test_topology['relations']), 0)

    @requests_mock.Mocker()
    def test_collect_processes(self, m):
        """
        Testing Dynatrace check should collect processes
        """
        self._set_http_responses(m, procs=read_file("process_response.json", "samples"))
        self.check.url = self.instance.get('url')
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        expected_topology = load_json_from_file("expected_process_topology.json", "samples")
        self.assert_topology(expected_topology, test_topology)

    @requests_mock.Mocker()
    def test_collect_hosts(self, m):
        """
        Testing Dynatrace check should collect hosts
        """
        self._set_http_responses(m, hosts=read_file("host_response.json", "samples"))
        self.check.url = self.instance.get('url')
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        expected_topology = load_json_from_file("expected_host_topology.json", "samples")
        self.assert_topology(expected_topology, test_topology)

    @requests_mock.Mocker()
    def test_collect_services(self, m):
        """
        Testing Dynatrace check should collect services and tags coming from Kubernetes
        """
        self._set_http_responses(m, svcs=read_file("service_response.json", "samples"))
        self.check.url = self.instance.get('url')
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        expected_topology = load_json_from_file("expected_service_topology.json", "samples")
        self.assert_topology(expected_topology, test_topology)

    def assert_topology(self, expected_topology, test_topology):
        """
        Sort the keys of components and relations, so we can actually match it
        :param expected_topology: expected topology read from file
        :param test_topology: topology gathered during test
        :return: None
        """
        components, relations = sort_topology_data(test_topology)
        expected_components, expected_relations = sort_topology_data(expected_topology)
        self.assertEqual(components, expected_components)
        self.assertEqual(len(relations), len(expected_relations))
        for relation in relations:
            self.assertIn(relation, expected_relations)

    @requests_mock.Mocker()
    def test_collect_applications(self, m):
        """
        Testing Dynatrace check should collect applications and also the tags properly coming from dynatrace
        """
        self._set_http_responses(m, apps=read_file("application_response.json", "samples"))
        self.check.url = self.instance.get('url')
        self.check.run()
        topo_instances = topology.get_snapshot(self.check.check_id)
        expected_topology = load_json_from_file("expected_application_topology.json", "samples")
        # sort the keys of components and relations, so we match it in actual
        self.assert_topology(expected_topology, topo_instances)

    @requests_mock.Mocker()
    def test_collect_process_groups(self, m):
        """
        Testing Dynatrace check should collect process-groups
        """
        self._set_http_responses(m, proc_groups=read_file("process-group_response.json", "samples"))
        self.check.url = self.instance.get('url')
        self.check.run()
        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = load_json_from_file("expected_process-group_topology.json", "samples")
        # sort the keys of components and relations, so we match it in actual
        self.assert_topology(actual_topology, topo_instances)

    @requests_mock.Mocker()
    def test_collect_relations(self, m):
        """
        Test to check if relations are collected properly
        """
        self._set_http_responses(m, hosts=read_file("host_response.json", "samples"))
        self.check.url = self.instance.get('url')
        self.check.run()
        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 2)
        self.assertEqual(len(topo_instances['relations']), 5)
        # since all relations are to this host itself so target id is same
        relation = topo_instances['relations'][0]
        self.assertEqual(relation['target_id'], 'HOST-6AAE0F78BCF2E0F4')
        self.assertIn(relation['type'], ['isProcessOf', 'runsOn'])

    @requests_mock.Mocker()
    def test_check_raise_exception(self, m):
        """
        Test to raise a check exception when collecting components and snapshot should be False
        """
        m.get("/api/v1/entity", exc=Exception("Exception occured"))

        self.assertRaises(Exception, self.check.run())
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
                                 hosts=read_file("host_response.json", "samples"),
                                 apps=read_file("application_response.json", "samples"),
                                 svcs=read_file("service_response.json", "samples"),
                                 procs=read_file("process_response.json", "samples"),
                                 proc_groups=read_file("process-group_response.json", "samples")
                                 )

        self.check.url = self.instance.get('url')
        self.check.run()

        expected_topology = load_json_from_file("expected_smartscape_full_topology.json", "samples")
        actual_topology = topology.get_snapshot(self.check.check_id)

        components, relations = sort_topology_data(actual_topology)
        expected_components, expected_relations = sort_topology_data(expected_topology)

        self.assertEqual(len(components), len(expected_components))
        for component in components:
            self.assertIn(component, expected_components)

        self.assertEqual(len(relations), len(expected_relations))
        for relation in relations:
            self.assertIn(relation, expected_relations)

    @requests_mock.Mocker()
    def test_collect_custom_devices(self, m):
        """
        Test Dynatrace check should produce custom devices
        """
        self._set_http_responses(m, dev=read_file("custom_device_response.json", "samples"))
        self.check.url = self.instance.get('url')
        self.check.run()
        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = load_json_from_file("expected_custom_device_topology.json", "samples")
        # sort the keys of components and relations, so we match it in actual
        self.assert_topology(actual_topology, topo_instances)

    @requests_mock.Mocker()
    def test_collect_custom_devices_with_pagination(self, m):
        """
        Test Dynatrace check should produce custom devices with pagination
        """
        self._set_http_responses(m)
        url = self.instance.get('url')
        first_url = url + "/api/v2/entities?entitySelector=type%28%22CUSTOM_DEVICE%22%29&from=now-1h&fields=%2B" \
                          "fromRelationships%2C%2BtoRelationships%2C%2Btags%2C%2BmanagementZones%2C%2B" \
                          "properties.dnsNames%2C%2Bproperties.ipAddress"
        second_url = url + "/api/v2/entities?nextPageKey=nextpageresultkey"
        m.get(first_url, status_code=200, text=read_file("custom_device_response_next_page.json", "samples"))
        m.get(second_url, status_code=200, text=read_file("custom_device_response.json", "samples"))
        self.check.run()
        topo_instances = topology.get_snapshot(self.check.check_id)
        actual_topology = load_json_from_file("expected_custom_device_pagination_full_topology.json", "samples")
        self.assert_topology(actual_topology, topo_instances)
