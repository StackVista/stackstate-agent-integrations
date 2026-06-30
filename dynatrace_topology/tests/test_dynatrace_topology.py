# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.common import read_file, load_json_from_file
from stackstate_checks.dynatrace_topology.entity_data_types import ProcessGroupInstanceEntity, ServiceEntity
from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
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
    With the new two-pass approach, only relations between entities in the cache are created.
    When only hosts are loaded, we only get isNetworkClientOfHost relations between hosts.
    """
    set_http_responses(requests_mock, hosts=read_file("host_response_v2.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_instances = topology.get_snapshot(dynatrace_check.check_id)
    assert len(topology_instances['components']) == 2
    # Filter relations to supported entity types, matching integration behavior
    SUPPORTED_PREFIXES = (
        'HOST-', 'PROCESS_GROUP-', 'PROCESS_GROUP_INSTANCE-', 'SERVICE-', 'APPLICATION-', 'CUSTOM_DEVICE-', 'QUEUE-',
        'SYNTHETIC_TEST-'
    )
    filtered = []
    for r in topology_instances['relations']:
        src = r.get('source_id', '') or ''
        tgt = r.get('target_id', '') or ''
        if any(src.startswith(p) for p in SUPPORTED_PREFIXES) and \
                any(tgt.startswith(p) for p in SUPPORTED_PREFIXES):
            filtered.append(r)
    topology_instances['relations'] = filtered
    # With cache verification, only relations between hosts are created
    # (no relations to non-existent process groups, services, etc.)
    assert len(topology_instances['relations']) == 4
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

    # Filter relations to only supported entity id prefixes to match integration behavior
    SUPPORTED_PREFIXES = (
        'HOST-', 'PROCESS_GROUP-', 'PROCESS_GROUP_INSTANCE-', 'SERVICE-', 'APPLICATION-', 'CUSTOM_DEVICE-', 'QUEUE-',
        'SYNTHETIC_TEST-'
    )

    def filter_supported_relations(top):
        rels = top.get('relations', []) or []
        filtered = []
        for r in rels:
            src = r.get('source_id', '') or ''
            tgt = r.get('target_id', '') or ''
        if (
                any(src.startswith(p) for p in SUPPORTED_PREFIXES)
                and any(tgt.startswith(p) for p in SUPPORTED_PREFIXES)
        ):
            filtered.append(r)
        top['relations'] = filtered
        return top

    expected_topology = filter_supported_relations(expected_topology)
    actual_topology = filter_supported_relations(actual_topology)

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


def test_custom_device_override_params(requests_mock, test_instance, aggregator, telemetry, topology, health, mocker):
    """
    Ensure custom device collection uses instance overrides for relative time and fields.
    """
    custom_instance = dict(test_instance)
    custom_instance["custom_device_relative_time"] = "30m"
    custom_instance["custom_device_fields"] = "+fromRelationships,+properties.customField"

    check = DynatraceTopologyCheck('dynatrace_topology', {}, instances=[custom_instance])
    mocker.patch(
        'stackstate_checks.dynatrace.dynatrace_client.DynatraceClientFactory.create_client',
        return_value=check.dynatrace_client_factory.create_client(
            instance_name=str(custom_instance.get('url')),
            token=custom_instance.get('token'),
            verify=custom_instance.get('verify', False),
            cert=custom_instance.get('cert'),
            keyfile=custom_instance.get('keyfile'),
            timeout=custom_instance.get('timeout')
        )
    )

    # Register default responses for all endpoints with a focus on the custom device query parameters.
    set_http_responses(requests_mock)
    custom_url = (
        custom_instance['url']
        + "/api/v2/entities?entitySelector=type%28%22CUSTOM_DEVICE%22%29&from=now-30m&fields=%2BfromRelationships"
          "%2C%2Bproperties.customField"
    )
    requests_mock.get(custom_url, status_code=200, text=read_file("custom_device_response.json", "samples"))

    check.run()

    custom_requests = [
        request for request in requests_mock.request_history
        if "api/v2/entities" in request.url and "CUSTOM_DEVICE" in request.url
    ]
    assert custom_requests, "Expected at least one custom device request"
    assert "from=now-30m" in custom_requests[0].url
    assert "%2Bproperties.customField" in custom_requests[0].url

    aggregator.reset()
    telemetry.reset()
    topology.reset()
    health.reset()
    check.commit_state(None)

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


def test_host_entity_osservices_dict_handling():
    """
    Test that HostEntity correctly handles osServices field when it's a list of dictionaries
    This reproduces the error:
      "Input should be a valid string [type=string_type, input_value={'dt.osservice.name': '...'}]"
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    # Test data that simulates the problematic case from the error
    test_data = {
        'entityId': 'HOST-0EA7023215644A24',
        'type': 'HOST',
        'displayName': 'test.example.com',
        'properties': {
            'osServices': [
                {
                    'dt.osservice.name': 'conjur-cluster',
                    'dt.osservice.startup_type': 'enabled',
                    'dt.entity.process_group_instance': 'PROCESS_GROUP_INSTANCE-8C88449DB803E9E6',
                    'dt.osservice.display_name': 'conjur-cluster',
                    'dt.osservice.path': '/usr/bin/conmon',
                    'dt.osservice.status': 'active',
                    'dt.osservice.alerting': 'true'
                },
                {
                    'dt.osservice.name': 'another-service',
                    'dt.osservice.display_name': 'Another Service',
                    'dt.osservice.status': 'inactive'
                }
            ]
        }
    }

    # This should not raise a validation error anymore
    entity = HostEntity.model_validate(test_data)

    # The list should have been converted to service names (strings)
    assert isinstance(entity.properties.osServices, list)
    assert len(entity.properties.osServices) == 2
    assert entity.properties.osServices[0] == 'conjur-cluster'
    assert entity.properties.osServices[1] == 'another-service'


def test_host_entity_osservices_string_handling():
    """
    Test that HostEntity still works correctly with string list osServices (original format)
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    # Test data with the original string list format
    test_data = {
        'entityId': 'HOST-TEST123',
        'type': 'HOST',
        'displayName': 'test.example.com',
        'properties': {
            'osServices': ['service1', 'service2', 'service3']
        }
    }

    # This should work as before
    entity = HostEntity.model_validate(test_data)

    # The string list should remain unchanged
    assert isinstance(entity.properties.osServices, list)
    assert entity.properties.osServices == ['service1', 'service2', 'service3']


def test_host_entity_osservices_mixed_handling():
    """
    Test that HostEntity handles mixed osServices formats (both dict and string)
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    # Test data with mixed formats
    test_data = {
        'entityId': 'HOST-TEST123',
        'type': 'HOST',
        'displayName': 'test.example.com',
        'properties': {
            'osServices': [
                'existing-string-service',
                {
                    'dt.osservice.name': 'new-dict-service',
                    'dt.osservice.display_name': 'New Dict Service'
                },
                'another-string-service'
            ]
        }
    }

    # This should handle both formats correctly
    entity = HostEntity.model_validate(test_data)

    # Both formats should be converted to strings
    assert isinstance(entity.properties.osServices, list)
    assert len(entity.properties.osServices) == 3
    assert entity.properties.osServices[0] == 'existing-string-service'
    assert entity.properties.osServices[1] == 'new-dict-service'
    assert entity.properties.osServices[2] == 'another-string-service'


def test_host_entity_osservices_fallback_name():
    """
    Test that HostEntity handles osServices dict without proper name fields
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    # Test data with dict missing both name and display_name
    test_data = {
        'entityId': 'HOST-TEST123',
        'type': 'HOST',
        'displayName': 'test.example.com',
        'properties': {
            'osServices': [
                {
                    'dt.osservice.status': 'active',
                    'dt.osservice.path': '/some/path'
                    # Missing both dt.osservice.name and dt.osservice.display_name
                }
            ]
        }
    }

    # This should use fallback name
    entity = HostEntity.model_validate(test_data)

    # Should use the fallback 'unknown_service_0' (with index for debugging)
    assert isinstance(entity.properties.osServices, list)
    assert len(entity.properties.osServices) == 1
    assert entity.properties.osServices[0] == 'unknown_service_0'


def test_process_group_entity_custompgmetadata_list_handling():
    """
    Test that ProcessGroupEntity correctly handles customPgMetadata field when it's a list of key-value objects
    This reproduces the error: "Input should be a valid dictionary [type=dict_type,
    input_value=[{'value': 'nginx', 'key': '...'}]]"
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import ProcessGroupEntity

    # Test data that simulates the problematic case from the error
    test_data = {
        'entityId': 'PROCESS_GROUP-TEST123',
        'type': 'PROCESS_GROUP',
        'displayName': 'Test Process Group',
        'properties': {
            'customPgMetadata': [
                {'key': 'application', 'value': 'nginx'},
                {'key': 'foundryBuildpackVersion', 'value': '1.2.3'},
                {'key': 'environment', 'value': 'production'}
            ]
        }
    }

    # This should not raise a validation error anymore
    entity = ProcessGroupEntity.model_validate(test_data)

    # The list should have been converted to a dictionary
    assert isinstance(entity.properties.customPgMetadata, dict)
    assert len(entity.properties.customPgMetadata) == 3
    assert entity.properties.customPgMetadata['application'] == 'nginx'
    assert entity.properties.customPgMetadata['foundryBuildpackVersion'] == '1.2.3'
    assert entity.properties.customPgMetadata['environment'] == 'production'


def test_process_group_entity_custompgmetadata_dict_handling():
    """
    Test that ProcessGroupEntity still works correctly with dictionary customPgMetadata (original format)
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import ProcessGroupEntity

    # Test data with the original dictionary format
    test_data = {
        'entityId': 'PROCESS_GROUP-TEST123',
        'type': 'PROCESS_GROUP',
        'displayName': 'Test Process Group',
        'properties': {
            'customPgMetadata': {
                'application': 'nginx',
                'version': '1.2.3',
                'environment': 'production'
            }
        }
    }

    # This should work as before
    entity = ProcessGroupEntity.model_validate(test_data)

    # The dictionary should remain unchanged
    assert isinstance(entity.properties.customPgMetadata, dict)
    assert entity.properties.customPgMetadata['application'] == 'nginx'
    assert entity.properties.customPgMetadata['version'] == '1.2.3'
    assert entity.properties.customPgMetadata['environment'] == 'production'


def test_process_group_entity_custompgmetadata_fallback_handling():
    """
    Test that ProcessGroupEntity handles customPgMetadata list with missing key/value fields
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import ProcessGroupEntity

    # Test data with malformed list items
    test_data = {
        'entityId': 'PROCESS_GROUP-TEST123',
        'type': 'PROCESS_GROUP',
        'displayName': 'Test Process Group',
        'properties': {
            'customPgMetadata': [
                {'key': 'valid_key', 'value': 'valid_value'},
                {'missing_key': 'something'},  # Missing 'key' field
                {'key': 'no_value_key'},  # Missing 'value' field
                'string_item'  # Not even a dict
            ]
        }
    }

    # This should handle malformed data gracefully
    entity = ProcessGroupEntity.model_validate(test_data)

    # Should create a dictionary with fallback keys/values
    assert isinstance(entity.properties.customPgMetadata, dict)
    assert entity.properties.customPgMetadata['valid_key'] == 'valid_value'
    assert 'unknown_key_1' in entity.properties.customPgMetadata  # Fallback for missing key
    assert entity.properties.customPgMetadata['no_value_key'] == 'unknown_value_2'  # Fallback for missing value
    assert 'item_3' in entity.properties.customPgMetadata  # Fallback for non-dict item


def test_process_group_entity_custompgmetadata_nonscalar_key():
    """
    Test that ProcessGroupEntity handles customPgMetadata list with a non-scalar key
    (e.g., dict or list) by falling back to an auto-generated key name.
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import ProcessGroupEntity

    test_data = {
        'entityId': 'PROCESS_GROUP-TEST123',
        'type': 'PROCESS_GROUP',
        'displayName': 'Test Process Group',
        'properties': {
            'customPgMetadata': [
                {'key': {'nested': 'dict'}, 'value': 'val1'},
                {'key': ['list', 'key'], 'value': 'val2'},
                {'key': {'source': 'KUBERNETES', 'key': 'cni.projectcalico.org/podIPs'}, 'value': '10.7.3.85/32'},
            ]
        }
    }

    entity = ProcessGroupEntity.model_validate(test_data)

    assert isinstance(entity.properties.customPgMetadata, dict)
    # Non-scalar keys without inner 'key' should map to fallback keys
    assert 'unknown_key_0' in entity.properties.customPgMetadata
    assert 'unknown_key_1' in entity.properties.customPgMetadata
    # Nested key dicts with inner 'key' should extract the string key
    assert entity.properties.customPgMetadata['cni.projectcalico.org/podIPs'] == '10.7.3.85/32'


def test_host_entity_customhostmetadata_list_handling():
    """
    Test that HostEntity tolerates customHostMetadata as a list of key-value objects.
    Reproduces the Rabobank production error (STAC-25137):
      "Input should be a valid dictionary [type=dict_type,
       input_value=[{'value': 'VM4', 'key': 'ENVIRONMENT'}, ...], input_type=list]"
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    test_data = {
        'entityId': 'HOST-0C4456C4494C5BF5',
        'type': 'HOST',
        'displayName': 'lspe003490.eu.rabonet.com',
        'properties': {
            'customHostMetadata': [
                {'value': 'VM4', 'key': 'ENVIRONMENT'},
                {'value': 'VM', 'key': 'VM'},
            ]
        }
    }

    # This must no longer raise a validation error; the host must not be dropped.
    entity = HostEntity.model_validate(test_data)

    # The list shape is preserved as-is (tolerant parse: dict -> list -> str).
    assert isinstance(entity.properties.customHostMetadata, list)
    assert entity.properties.customHostMetadata == [
        {'value': 'VM4', 'key': 'ENVIRONMENT'},
        {'value': 'VM', 'key': 'VM'},
    ]
    # Downstream serialization (used to build topology) must succeed and keep the shape.
    dumped = entity.model_dump(mode="json", exclude_none=True)
    assert dumped['properties']['customHostMetadata'] == [
        {'value': 'VM4', 'key': 'ENVIRONMENT'},
        {'value': 'VM', 'key': 'VM'},
    ]


def test_host_entity_customhostmetadata_dict_handling():
    """
    Test that HostEntity still accepts customHostMetadata as a dict (original/mock format).
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    test_data = {
        'entityId': 'HOST-0C4456C4494C5BF5',
        'type': 'HOST',
        'displayName': 'lspe003490.eu.rabonet.com',
        'properties': {
            'customHostMetadata': {
                'ENVIRONMENT': 'VM4',
                'VM': 'VM',
            }
        }
    }

    entity = HostEntity.model_validate(test_data)

    assert isinstance(entity.properties.customHostMetadata, dict)
    assert entity.properties.customHostMetadata['ENVIRONMENT'] == 'VM4'
    assert entity.properties.customHostMetadata['VM'] == 'VM'


def test_host_entity_customhostmetadata_string_handling():
    """
    Test that HostEntity tolerates customHostMetadata delivered as a plain string.
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    test_data = {
        'entityId': 'HOST-0C4456C4494C5BF5',
        'type': 'HOST',
        'displayName': 'lspe003490.eu.rabonet.com',
        'properties': {
            'customHostMetadata': 'ENVIRONMENT=VM4'
        }
    }

    entity = HostEntity.model_validate(test_data)

    assert isinstance(entity.properties.customHostMetadata, str)
    assert entity.properties.customHostMetadata == 'ENVIRONMENT=VM4'


def test_host_entity_customhostmetadata_other_type_fallback():
    """
    Test that a customHostMetadata value that is neither dict, list nor string falls back
    to its string representation instead of dropping the host entity.
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    test_data = {
        'entityId': 'HOST-0C4456C4494C5BF5',
        'type': 'HOST',
        'displayName': 'lspe003490.eu.rabonet.com',
        'properties': {
            'customHostMetadata': 42
        }
    }

    entity = HostEntity.model_validate(test_data)

    assert isinstance(entity.properties.customHostMetadata, str)
    assert entity.properties.customHostMetadata == '42'


def test_entity_cache_resets_between_runs(requests_mock, dynatrace_check, topology, aggregator):
    """
    Verify that the in-memory entity cache is cleared at the start of each check run.
    First run: provide some entities -> cache should be > 0 after run.
    Second run: provide no entities -> cache should be exactly 0, proving it was reset.
    """
    # First run with hosts payload (non-empty)
    set_http_responses(requests_mock, hosts=read_file("host_response_v2.json", "samples"))
    dynatrace_check.run()
    assert len(dynatrace_check.dynatrace_entities_cache) > 0

    # Second run with empty responses
    aggregator.reset()
    topology.reset()
    requests_mock.reset()
    set_http_responses(requests_mock)  # defaults to empty for all endpoints
    dynatrace_check.run()
    assert len(dynatrace_check.dynatrace_entities_cache) == 0


def test_host_entity_logfilestatus_list_handling():
    """
    Test that logFileStatus as a list is properly wrapped into expected structure.
    Dynatrace API can return logFileStatus as a list, but the model expects a dict wrapper.
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    # Simulate the raw data structure from Dynatrace API
    raw_host = {
        "entityId": "HOST-123456789",
        "type": "HOST",
        "displayName": "test-host",
        "properties": {
            "logFileStatus": [
                {"value": "FILE_STATUS_OK", "key": "/var/log/application/app_batch.log"}
            ]
        }
    }

    # Apply the transformation that _clean_unsupported_metadata would do
    from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
    check = DynatraceTopologyCheck('dynatrace', {}, [])
    cleaned = check._clean_unsupported_metadata(raw_host)

    # Verify the transformation wrapped the list
    assert "logFileStatus" in cleaned["properties"]
    assert isinstance(cleaned["properties"]["logFileStatus"], dict)
    assert "logFileStatus" in cleaned["properties"]["logFileStatus"]
    assert isinstance(cleaned["properties"]["logFileStatus"]["logFileStatus"], list)

    # Now validate it with the model
    host_entity = HostEntity.model_validate(cleaned)
    assert host_entity.entityId == "HOST-123456789"
    assert host_entity.properties.logFileStatus is not None
    assert hasattr(host_entity.properties.logFileStatus, 'logFileStatus')


def test_host_entity_logsourcestate_list_handling():
    """
    Test that logSourceState as a list is properly wrapped into expected structure.
    Dynatrace API can return logSourceState as a list, but the model expects a dict wrapper.
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    # Simulate the raw data structure from Dynatrace API
    raw_host = {
        "entityId": "HOST-987654321",
        "type": "HOST",
        "displayName": "test-host-2",
        "properties": {
            "logSourceState": [
                {"value": {"storageStatus": "STORAGE_OK"}, "key": "/var/log/application/app_batch.log"}
            ]
        }
    }

    # Apply the transformation that _clean_unsupported_metadata would do
    from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
    check = DynatraceTopologyCheck('dynatrace', {}, [])
    cleaned = check._clean_unsupported_metadata(raw_host)

    # Verify the transformation wrapped the list
    assert "logSourceState" in cleaned["properties"]
    assert isinstance(cleaned["properties"]["logSourceState"], dict)
    assert "logSourceState" in cleaned["properties"]["logSourceState"]
    assert isinstance(cleaned["properties"]["logSourceState"]["logSourceState"], list)

    # Now validate it with the model
    host_entity = HostEntity.model_validate(cleaned)
    assert host_entity.entityId == "HOST-987654321"
    assert host_entity.properties.logSourceState is not None
    assert hasattr(host_entity.properties.logSourceState, 'logSourceState')


def test_host_entity_logfilestatus_and_logsourcestate_combined():
    """
    Test handling both logFileStatus and logSourceState together.
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    # Simulate the exact scenario
    raw_host = {
        "entityId": "HOST-CUSTOMER123",
        "type": "HOST",
        "displayName": "customer-host",
        "properties": {
            "logFileStatus": [
                {"value": "FILE_STATUS_OK", "key": "/var/log/application/app_batch.log"}
            ],
            "logSourceState": [
                {"value": {"storageStatus": "STORAGE_OK"}, "key": "/var/log/application/app_batch.log"}
            ]
        }
    }

    # Apply the transformation
    from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
    check = DynatraceTopologyCheck('dynatrace', {}, [])
    cleaned = check._clean_unsupported_metadata(raw_host)

    # Verify both transformations
    assert isinstance(cleaned["properties"]["logFileStatus"], dict)
    assert isinstance(cleaned["properties"]["logSourceState"], dict)

    # Validate with the model - this should not raise validation errors
    host_entity = HostEntity.model_validate(cleaned)
    assert host_entity.entityId == "HOST-CUSTOMER123"
    assert host_entity.properties.logFileStatus is not None
    assert host_entity.properties.logSourceState is not None


def test_management_zones_in_labels():
    """
    Test handling both logFileStatus and logSourceState together.
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity

    # Simulate the exact scenario
    raw_host = {
        "entityId": "HOST-CUSTOMER123",
        "type": "HOST",
        "displayName": "customer-host",
        "properties": {
            "logFileStatus": [
                {"value": "FILE_STATUS_OK", "key": "/var/log/application/app_batch.log"}
            ],
            "logSourceState": [
                {"value": {"storageStatus": "STORAGE_OK"}, "key": "/var/log/application/app_batch.log"}
            ]
        },
        "managementZones": [
            {
                "id": "2414109248746337189",
                "name": "PROD_ZONE"
            },
            {
                "id": "5849059329244275694",
                "name": "APP_PROD_ZONE"
            }
        ]
    }

    # Apply the transformation
    from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
    check = DynatraceTopologyCheck('dynatrace', {}, [])
    cleaned = check._clean_unsupported_metadata(raw_host)

    host_entity = HostEntity.model_validate(cleaned)

    labels = check._get_labels(host_entity)
    assert "managementZones:PROD_ZONE" in labels
    assert "managementZones:APP_PROD_ZONE" in labels
    assert host_entity.entityId in labels


def test_software_technologies_labels_from_properties():
    """
    Ensure labels include software technologies present only inside properties.
    """
    from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck

    service_data = {
        "entityId": "SERVICE-EXAMPLE",
        "type": "SERVICE",
        "displayName": "example-service",
        "properties": {
            "softwareTechnologies": [
                {"type": "MYSQL"},
                {"type": "GO", "version": "1.19.13"},
                {"type": "NGINX", "edition": "FPM", "version": "1.27.0"}
            ]
        },
        "tags": [],
        "managementZones": [],
        "fromRelationships": {},
        "toRelationships": {}
    }

    service_entity = ServiceEntity.model_validate(service_data)
    check = DynatraceTopologyCheck('dynatrace', {}, [])

    labels = check._get_labels(service_entity)

    expected_labels = {"MYSQL", "GO:1.19.13", "NGINX:1.27.0", service_entity.entityId}
    assert expected_labels.issubset(set(labels))


def test_validation_error_skips_entity_gracefully(requests_mock, dynatrace_check, topology, aggregator):
    """
    Test that when an entity fails validation, it's skipped with a warning instead of crashing.
    The integration should continue processing other valid entities.
    """
    # Create a response with one invalid host (missing required 'type' field) and one valid host
    invalid_and_valid_hosts = {
        "totalCount": 2,
        "pageSize": 2,
        "entities": [
            {
                # Invalid host - missing required 'type' field
                "entityId": "HOST-INVALID123",
                # "type": "HOST",  # <- intentionally missing to cause validation error
                "displayName": "invalid-host.example.com",
                "properties": {},
                "tags": [],
                "managementZones": [],
                "fromRelationships": {},
                "toRelationships": {}
            },
            {
                # Valid host
                "entityId": "HOST-VALID456",
                "type": "HOST",
                "displayName": "valid-host.example.com",
                "properties": {},
                "tags": [],
                "managementZones": [],
                "fromRelationships": {},
                "toRelationships": {}
            }
        ]
    }

    import json
    set_http_responses(requests_mock, hosts=json.dumps(invalid_and_valid_hosts))
    dynatrace_check.run()

    # Check should still succeed (not crash)
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)

    # Should have logged a warning about the invalid entity
    # (Note: can't easily assert log messages in this test framework, but the check shouldn't crash)

    # Should have processed the valid host
    test_topology = topology.get_snapshot(dynatrace_check.check_id)

    # At least the valid host should be in the topology
    assert len(test_topology['components']) >= 1

    # Verify the valid host is present
    valid_host_found = any(
        comp['id'] == 'HOST-VALID456'
        for comp in test_topology['components']
    )
    assert valid_host_found, "Valid host should be present in topology"

    # Invalid host should NOT be in topology
    invalid_host_found = any(
        comp['id'] == 'HOST-INVALID123'
        for comp in test_topology['components']
    )
    assert not invalid_host_found, "Invalid host should have been skipped"


def test_problematic_host_data():
    """
    Test with the exact problematic data that was causing validation errors.
    This ensures our fix handles the scenario with logFileStatus and logSourceState as lists.
    """
    from stackstate_checks.dynatrace_topology.entity_data_types import HostEntity
    from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck

    host_data = {
        'entityId': 'HOST-E150D16FDF9B703F',
        'type': 'HOST',
        'displayName': 'host001.eu.yournamehere.com',
        'properties': {
            'bitness': '64',
            'installerTrackedDownload': False,
            'autoInjection': 'ENABLED',
            'additionalSystemInfo': [
                {'value': '0', 'key': 'system.processor.frequency.max'},
                {'value': 'No Enclosure', 'key': 'system.vendor'},
                {'value': 'None', 'key': 'system.serial'},
                {'value': 'Intel Corporation', 'key': 'system.board.vendor'},
                {'value': 'None', 'key': 'system.board.serial'},
                {'value': '0', 'key': 'system.processor.frequency.min'},
                {'value': '3810144256', 'key': 'system.memory.size'},
                {'value': 'Intel(R) Xeon(R) Gold 6342 CPU @ 2.80GHz', 'key': 'system.processor.model'},
                {'value': 'VMware Virtual Platform', 'key': 'system.model'},
                {'value': 'x86', 'key': 'system.architecture'}
            ],
            'monitoringMode': 'FULL_STACK',
            'osArchitecture': 'X86',
            'logFileStatus': [{'value': 'FILE_STATUS_OK', 'key': '/appl/tzx/p01/logs/application/app_batch.log'}],
            'osVersion': 'Red Hat Enterprise Linux 8.10 (Ootpa) (kernel 4.18.0-553.77.1.el8_10.x86_64)',
            'installerPotentialProblem': False,
            'macAddresses': ['00:50:56:8B:A5:FE'],
            'osType': 'LINUX',
            'state': 'RUNNING',
            'logSourceState': [
                {
                    'value': {'storageStatus': 'LOG_STORAGE_CONFIGURATION_STATUS_NOT_SEND_TO_STORAGE'},
                    'key': '/appl/tzx/p01/logs/application/app_batch.log'
                }
            ],
            'physicalMemory': 3810144256,
            'detectedName': 'host001.eu.yournamehere.com',
            'installerVersion': '1.321.51.20250905-075429',
            'standalone': False,
            'ipAddress': ['10.251.108.227'],
            'hypervisorType': 'VMWARE',
            'hostGroupName': 'PROD_APP_GROUP',
            'networkZone': 'default',
            'standaloneSpecialAgentsOnly': False,
            'isMonitoringCandidate': False,
            'logicalCpuCores': 2,
            'cpuCores': 2,
            'ebpfDiscoveryMonitored': False,
            'memoryTotal': 3810144256,
            'installerSupportAlert': False
        },
        'tags': [],
        'managementZones': [
            {
                'id': '2414109248746337189',
                'name': 'PROD_ZONE',
                'sourceSetting': (
                    'api/v2/settings/objects/'
                    'vu9U3hXa3q0AAAABABhidWlsdGluOm1hbmFnZW1lbnQtem9uZXMABnRlbmFudAAGdGVuYW50ACRjYWNlOTVjOC1jN2U0LTQ3N'
                    'DYtYWVkZi1iZDAwZDE4MDQzMjm-71TeFdrerQ'
                )
            },
            {
                'id': '5849059329244275694',
                'name': 'APP_PROD_ZONE',
                'sourceSetting': (
                    'api/v2/settings/objects/'
                    'vu9U3hXa3q0AAAABABhidWlsdGluOm1hbmFnZW1lbnQtem9uZXMABnRlbmFudAAGdGVuYW50ACRkYzhmZDFkYy04YzllLTRk'
                    'YzYtYTYyZi0zMDlmODRhY2EyMDG-71TeFdrerQ'
                )
            }
        ],
        'fromRelationships': {
            'isNetworkClientOfHost': [{'id': 'HOST-E150D16FDF9B703F', 'type': 'HOST'}],
            'isInstanceOf': [{'id': 'HOST_GROUP-E7C43DD053FA4A06', 'type': 'HOST_GROUP'}]
        },
        'toRelationships': {
            'isSiteOf': [{'id': 'GEOLOC_SITE-E6604F565A4E0689', 'type': 'GEOLOC_SITE'}],
            'isNetworkClientOfHost': [{'id': 'HOST-E150D16FDF9B703F', 'type': 'HOST'}],
            'runsOn': [{'id': 'PROCESS_GROUP-F3202EC588CC331F', 'type': 'PROCESS_GROUP'}],
            'isProcessOf': [{'id': 'PROCESS_GROUP_INSTANCE-3B022A3E5375F37E', 'type': 'PROCESS_GROUP_INSTANCE'}],
            'isDiskOf': [{'id': 'DISK-F5C353D06BCB7AC6', 'type': 'DISK'}],
            'isNetworkInterfaceOf': [{'id': 'NETWORK_INTERFACE-E150D13F8910D5C1', 'type': 'NETWORK_INTERFACE'}]
        }
    }

    # Apply the transformation that _clean_unsupported_metadata would do
    check = DynatraceTopologyCheck('dynatrace', {}, [])
    cleaned = check._clean_unsupported_metadata(host_data)

    # Verify the transformation worked
    assert "logFileStatus" in cleaned["properties"]
    assert isinstance(cleaned["properties"]["logFileStatus"], dict)
    assert "logFileStatus" in cleaned["properties"]["logFileStatus"]
    assert isinstance(cleaned["properties"]["logFileStatus"]["logFileStatus"], list)

    assert "logSourceState" in cleaned["properties"]
    assert isinstance(cleaned["properties"]["logSourceState"], dict)
    assert "logSourceState" in cleaned["properties"]["logSourceState"]
    assert isinstance(cleaned["properties"]["logSourceState"]["logSourceState"], list)

    # Now validate it with the model - this should NOT raise validation errors
    host_entity = HostEntity.model_validate(cleaned)
    assert host_entity.entityId == "HOST-E150D16FDF9B703F"
    assert host_entity.displayName == "host001.eu.yournamehere.com"
    assert host_entity.properties.logFileStatus is not None
    assert host_entity.properties.logSourceState is not None

    # Verify the data structure is correct
    assert len(host_entity.properties.logFileStatus.logFileStatus) == 1
    assert host_entity.properties.logFileStatus.logFileStatus[0].value == "FILE_STATUS_OK"
    assert host_entity.properties.logFileStatus.logFileStatus[0].key == "/appl/tzx/p01/logs/application/app_batch.log"

    assert len(host_entity.properties.logSourceState.logSourceState) == 1
    assert (host_entity.properties.logSourceState.logSourceState[0].value.storageStatus ==
            "LOG_STORAGE_CONFIGURATION_STATUS_NOT_SEND_TO_STORAGE")
    assert host_entity.properties.logSourceState.logSourceState[0].key == "/appl/tzx/p01/logs/application/app_batch.log"
