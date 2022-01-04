# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.common import read_file, load_json_from_file
from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
from .conftest import set_http_responses, sort_topology_data, assert_topology


def test_collect_empty_topology(requests_mock, dynatrace_check, topology):
    """
    Testing Dynatrace check should not produce any topology
    """
    set_http_responses(requests_mock)
    dynatrace_check.run()
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    assert len(test_topology['components']) == 0
    assert len(test_topology['relations']) == 0


def test_collect_processes(requests_mock, dynatrace_check, topology):
    """
    Testing Dynatrace check should collect processes
    """
    set_http_responses(requests_mock, processes=read_file("process_response.json", "samples"))
    dynatrace_check.run()
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_process_topology.json", "samples")
    assert_topology(expected_topology, test_topology)


def test_collect_hosts(requests_mock, dynatrace_check, topology):
    """
    Testing Dynatrace check should collect hosts
    """
    set_http_responses(requests_mock, hosts=read_file("host_response.json", "samples"))
    dynatrace_check.run()
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_host_topology.json", "samples")
    assert_topology(expected_topology, test_topology)


def test_collect_services(requests_mock, dynatrace_check, topology):
    """
    Testing Dynatrace check should collect services and tags coming from Kubernetes
    """
    set_http_responses(requests_mock, services=read_file("service_response.json", "samples"))
    dynatrace_check.run()
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_service_topology.json", "samples")
    assert_topology(expected_topology, test_topology)


def test_collect_applications(dynatrace_check, requests_mock, topology):
    """
    Testing Dynatrace check should collect applications and also the tags properly coming from dynatrace
    """
    set_http_responses(requests_mock, applications=read_file("application_response.json", "samples"))
    dynatrace_check.run()
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_application_topology.json", "samples")
    assert_topology(expected_topology, topology_instances)


def test_collect_process_groups(dynatrace_check, requests_mock, topology):
    """
    Testing Dynatrace check should collect process-groups
    """
    set_http_responses(requests_mock, process_groups=read_file("process-group_response.json", "samples"))
    dynatrace_check.run()
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_process-group_topology.json", "samples")
    assert_topology(expected_topology, topology_instances)


def test_collect_relations(dynatrace_check, requests_mock, topology):
    """
    Test to check if relations are collected properly
    """
    set_http_responses(requests_mock, hosts=read_file("host_response.json", "samples"))
    dynatrace_check.run()
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    assert len(topology_instances['components']) == 2
    assert len(topology_instances['relations']) == 5
    # since all relations are to this host itself so target id is same
    relation = topology_instances['relations'][0]
    assert relation['target_id'] == 'HOST-6AAE0F78BCF2E0F4'
    assert relation['type'] in ['isProcessOf', 'runsOn']


def test_check_raise_exception(dynatrace_check, topology, aggregator):
    """
    Test to raise a check exception when collecting components and snapshot should be False
    """
    # we don't mock requests, so check will raise exception
    # No mock address: GET https://instance.live.dynatrace.com/api/v1/entity/infrastructure/processes
    dynatrace_check.run()
    # since the check raised exception, the topology snapshot is not completed
    topology_instance = topology.get_snapshot(dynatrace_check.check_id)
    assert topology_instance.get("start_snapshot") is True
    assert topology_instance.get("stop_snapshot") is False
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL)


def test_full_topology(dynatrace_check, requests_mock, topology):
    """
    Test e2e to collect full topology for all component types from Dynatrace
    """
    set_http_responses(requests_mock,
                       hosts=read_file("host_response.json", "samples"),
                       applications=read_file("application_response.json", "samples"),
                       services=read_file("service_response.json", "samples"),
                       processes=read_file("process_response.json", "samples"),
                       process_groups=read_file("process-group_response.json", "samples"))

    dynatrace_check.run()

    expected_topology = load_json_from_file("expected_smartscape_full_topology.json", "samples")
    actual_topology = topology.get_snapshot(dynatrace_check.check_id)

    components, relations = sort_topology_data(actual_topology)
    expected_components, expected_relations = sort_topology_data(expected_topology)

    assert len(components) == len(expected_components)
    for component in components:
        assert component in expected_components
    assert len(relations) == len(expected_relations)
    for relation in relations:
        assert relation in expected_relations


def test_collect_custom_devices(dynatrace_check, requests_mock, topology):
    """
    Test Dynatrace check should produce custom devices
    """
    set_http_responses(requests_mock, entities=read_file("custom_device_response.json", "samples"))
    dynatrace_check.run()
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_custom_device_topology.json", "samples")
    assert_topology(expected_topology, topology_instances)


def test_collect_custom_devices_with_pagination(dynatrace_check, requests_mock, test_instance, topology):
    """
    Test Dynatrace check should produce custom devices with pagination
    """
    set_http_responses(requests_mock)
    url = test_instance.get('url')
    first_url = url + "/api/v2/entities?entitySelector=type%28%22CUSTOM_DEVICE%22%29&from=now-1h&fields=%2B" \
                      "fromRelationships%2C%2BtoRelationships%2C%2Btags%2C%2BmanagementZones%2C%2B" \
                      "properties.dnsNames%2C%2Bproperties.ipAddress"
    second_url = url + "/api/v2/entities?nextPageKey=nextpageresultkey"
    requests_mock.get(first_url, status_code=200, text=read_file("custom_device_response_next_page.json", "samples"))
    requests_mock.get(second_url, status_code=200, text=read_file("custom_device_response.json", "samples"))
    dynatrace_check.run()
    snapshot = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_custom_device_pagination_full_topology.json", "samples")
    assert_topology(expected_topology, snapshot)


def test_relative_time_param(aggregator, requests_mock, test_instance, test_instance_relative_time):
    # create check with instance that has 'day' relative time setting
    check = DynatraceTopologyCheck('dynatrace', {}, {}, instances=[test_instance_relative_time])
    check.run()
    # no mock calls, so check fails
    aggregator.assert_service_check(check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL)
    assert '?relativeTime=day' in aggregator.service_checks('dynatrace-topology')[0].message

    # create another check with default setting
    aggregator.reset()
    another_check = DynatraceTopologyCheck('dynatrace', {}, {}, instances=[test_instance])
    another_check.run()
    # no mock calls, so check fails
    aggregator.assert_service_check(another_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL)
    assert '?relativeTime=hour' in aggregator.service_checks('dynatrace-topology')[0].message
