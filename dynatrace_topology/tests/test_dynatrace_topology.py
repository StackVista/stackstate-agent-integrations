# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.common import read_file, load_json_from_file
from stackstate_checks.dynatrace_topology.entity_data_types import ProcessGroupInstanceEntity
from .conftest import set_http_responses, sort_topology_data, assert_topology


def test_collect_empty_topology(requests_mock, dynatrace_check, topology, aggregator):
    """
    Testing Dynatrace check should not produce any topology
    """
    set_http_responses(requests_mock)
    dynatrace_check.run()
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    assert len(test_topology['components']) == 0
    assert len(test_topology['relations']) == 0


def test_collect_processes(requests_mock, dynatrace_check, topology, aggregator):
    """
    Testing Dynatrace check should collect processes
    """
    set_http_responses(requests_mock, processes=read_file("process_response_v2.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_process_topology_v2.json", "samples")
    assert_topology(expected_topology, test_topology)


def test_collect_hosts(requests_mock, dynatrace_check, topology, aggregator):
    """
    Testing Dynatrace check should collect hosts
    """
    set_http_responses(requests_mock, hosts=read_file("host_response_v2.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_host_topology_v2.json", "samples")
    assert_topology(expected_topology, test_topology)


def test_collect_services(requests_mock, dynatrace_check, topology, aggregator):
    """
    Testing Dynatrace check should collect services and tags coming from Kubernetes
    """
    set_http_responses(requests_mock, services=read_file("service_response_v2.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_service_topology_v2.json", "samples")
    assert_topology(expected_topology, test_topology)


def test_collect_applications(dynatrace_check, requests_mock, topology, aggregator):
    """
    Testing Dynatrace check should collect applications and also the tags properly coming from dynatrace
    """
    set_http_responses(requests_mock, applications=read_file("application_response_v2.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_application_topology_v2.json", "samples")
    assert_topology(expected_topology, topology_instances)


def test_collect_process_groups(dynatrace_check, requests_mock, topology, aggregator):
    """
    Testing Dynatrace check should collect process-groups
    """
    set_http_responses(requests_mock, process_groups=read_file("process-group_response_v2.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_process-group_topology_v2.json", "samples")
    assert_topology(expected_topology, topology_instances)


def test_collect_relations(dynatrace_check, requests_mock, topology, aggregator):
    """
    Test to check if relations are collected properly
    """
    set_http_responses(requests_mock, hosts=read_file("host_response_v2.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    assert len(topology_instances['components']) == 2
    assert len(topology_instances['relations']) == 94
    # since all relations are to this host itself so target id is same
    relation = topology_instances['relations'][0]
    assert relation['target_id'] == 'HOST-27D021F0FED92055'
    assert relation['type'] in ['isProcessOf', 'runsOn', 'isNetworkClientOfHost']


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


def test_full_topology(dynatrace_check, requests_mock, topology, aggregator):
    """
    Test e2e to collect full topology for all component types from Dynatrace
    """
    import json
    from deepdiff import DeepDiff

    set_http_responses(
        requests_mock,
        hosts=read_file("host_response_v3.json", "samples"),
        applications=read_file("application_response_v3.json", "samples"),
        services=read_file("service_response_v3.json", "samples"),
        processes=read_file("process_response_v3.json", "samples"),
        process_groups=read_file("process-group_response_v3.json", "samples")
    )

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)

    expected_topology = load_json_from_file("expected_smartscape_full_topology_v2.json", "samples")
    actual_topology = topology.get_snapshot(dynatrace_check.check_id)

    components, relations = sort_topology_data(actual_topology)
    expected_components, expected_relations = sort_topology_data(expected_topology)

    assert len(components) == len(
        expected_components), f"Expected {len(expected_components)} components, got {len(components)}."

    def normalize(data):
        if isinstance(data, dict):
            return {k: normalize(v) for k, v in sorted(data.items())}
        elif isinstance(data, list):
            return sorted([normalize(item) for item in data], key=lambda x: json.dumps(x, sort_keys=True))
        else:
            return data

    parsed_components = [json.loads(comp) for comp in components]
    parsed_expected = [json.loads(exp) for exp in expected_components]

    normalized_components = [normalize(comp) for comp in parsed_components]
    normalized_expected = [normalize(exp) for exp in parsed_expected]

    for idx, component in enumerate(normalized_components):
        if component not in normalized_expected:
            print(f"Component at index {idx} not found in expected_components:")
            print(json.dumps(parsed_components[idx], indent=2))

            # Find and display specific differences
            for exp_idx, exp in enumerate(normalized_expected):
                diff = DeepDiff(exp, component, ignore_order=True)
                if not diff:
                    continue  # Exact match found elsewhere
                print(f"Differences with expected_components[{exp_idx}]: {diff}")

            raise AssertionError(f"Component at index {idx} not found in expected_components.")


def test_collect_custom_devices(dynatrace_check, requests_mock, topology, aggregator):
    """
    Test Dynatrace check should produce custom devices
    """
    set_http_responses(requests_mock, custom_devices=read_file("custom_device_response.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)

    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_custom_device_topology.json", "samples")
    assert_topology(expected_topology, topology_instances)


def test_collect_custom_devices_with_pagination(dynatrace_check, requests_mock, test_instance, topology, aggregator):
    """
    Test Dynatrace check should produce custom devices with pagination
    """
    set_http_responses(requests_mock)
    url = test_instance.get('url')
    first_url = url + ("/api/v2/entities?entitySelector=type%28%22CUSTOM_DEVICE%22%29&from=now-1h&fields=%2BfromRelati"
                       "onships%2C%2BtoRelationships%2C%2Btags%2C%2BmanagementZones%2C%2Bproperties.dnsNames%2C%2Bprop"
                       "erties.ipAddress")
    second_url = url + "/api/v2/entities?nextPageKey=nextpageresultkey"
    requests_mock.get(first_url, status_code=200, text=read_file("custom_device_response_next_page.json",
                                                                 "samples"))
    requests_mock.get(second_url, status_code=200, text=read_file("custom_device_response.json",
                                                                  "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    snapshot = topology.get_snapshot(dynatrace_check.check_id)
    expected_topology = load_json_from_file("expected_custom_device_pagination_full_topology.json",
                                            "samples")
    assert_topology(expected_topology, snapshot)


# def test_relative_time_param(aggregator, requests_mock, test_instance, test_instance_relative_time):
#     # create check with instance that has 'day' relative time setting
#     check = DynatraceTopologyCheck('dynatrace', {}, {}, instances=[test_instance_relative_time])
#     check.run()
#     # no mock calls, so check fails
#     aggregator.assert_service_check(check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL)
#     assert '?relativeTime=day' in aggregator.service_checks('dynatrace-topology')[0].message
#
#     # create another check with default setting
#     aggregator.reset()
#     another_check = DynatraceTopologyCheck('dynatrace', {}, {}, instances=[test_instance])
#     another_check.run()
#     # no mock calls, so check fails
#     aggregator.assert_service_check(another_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL)
#     assert '?relativeTime=hour' in aggregator.service_checks('dynatrace-topology')[0].message


def test_applications_to_monitors_relations(requests_mock, dynatrace_check, topology, aggregator):
    """
    Testing Dynatrace check should collect applications and synthetic monitors relationship
    """
    set_http_responses(requests_mock, applications=read_file("application_response_synthetic_monitor.json",
                                                             "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    relations = topology_instances["relations"]

    for relation in relations:
        if relation["type"] == "monitors":
            assert "APPLICATION" in relation["source_id"]
            assert "SYNTHETIC_TEST" in relation["target_id"]


def test_process_group_instance_entity_releasesversion_string_handling():
    """
    Test that ProcessGroupInstanceEntity correctly handles releasesVersion field when it's a string
    This reproduces the error:
        "Input should be a valid dictionary [type=dict_type, input_value="ReleaseVersionInfo{...}"]"
    """
    # Test data that simulates the problematic case from the error
    test_data = {
        'entityId': 'PROCESS_GROUP_INSTANCE-TEST123',
        'type': 'PROCESS_GROUP_INSTANCE',
        'displayName': 'Test Process',
        'properties': {
            'releasesVersion': 'ReleaseVersionInfo{versi..._REGISTRY, timestamp=0}'
        }
    }

    # This should not raise a validation error anymore
    entity = ProcessGroupInstanceEntity.model_validate(test_data)

    # The string should have been converted to an empty dict
    assert isinstance(entity.properties.releasesVersion, dict)
    assert entity.properties.releasesVersion == {}


def test_process_group_instance_entity_releasesversion_dict_handling():
    """
    Test that ProcessGroupInstanceEntity still works correctly with dictionary releasesVersion
    """
    # Test data with a proper dictionary
    test_data = {
        'entityId': 'PROCESS_GROUP_INSTANCE-TEST123',
        'type': 'PROCESS_GROUP_INSTANCE',
        'displayName': 'Test Process',
        'properties': {
            'releasesVersion': {'version': '1.0', 'type': 'REGISTRY'}
        }
    }

    # This should work as before
    entity = ProcessGroupInstanceEntity.model_validate(test_data)

    # The dict should remain unchanged
    assert isinstance(entity.properties.releasesVersion, dict)
    assert entity.properties.releasesVersion == {'version': '1.0', 'type': 'REGISTRY'}
