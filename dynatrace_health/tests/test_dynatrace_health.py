# -*- coding: utf-8 -*-

# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import os
import re

import requests
from freezegun import freeze_time

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.common import read_file
from .conftest import set_http_responses


def _get_varied_event_by_type(event_type):
    """
    Helper function to extract a single event from the varied_events_response.json
    """
    events_response = json.loads(read_file('varied_events_response.json', 'samples'))
    for event in events_response['events']:
        if event['eventType'] == event_type:
            return event
    return None


def _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200):
    """
    Helper function to mock the events endpoint with regex pattern matching
    This allows tests to work regardless of the exact timestamp value
    """
    events_url_pattern = re.compile(r'{}/api/v2/events\?from=\d+'.format(re.escape(test_instance['url'])))
    # Handle both dict and string responses
    if isinstance(event_response, str):
        requests_mock.get(events_url_pattern, status_code=status_code, text=event_response)
    else:
        requests_mock.get(events_url_pattern, status_code=status_code, text=json.dumps(event_response))


@freeze_time('2025-07-22 08:26:24')
def test_availability_event(dynatrace_check, test_instance, requests_mock, health, aggregator):
    os.environ["JWT_AUTH"] = "false"
    event_type = "AVAILABILITY_EVENT"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_availability.json', 'samples')
    set_http_responses(requests_mock, availability_event=event_type_response)
    _mock_events_endpoint(requests_mock, test_instance, event_response)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    expected_check_state = {
        'checkStateId': 'APPLICATION-123456', 'health': 'CRITICAL', 'name': 'Dynatrace event',
        'message': 'Event: Availability Event Severity: AVAILABILITY Impact: APPLICATION Open Since: '
                   'Mar 15, 2023, 13:20:00 Source: builtin',
        'topologyElementIdentifier': 'urn:dynatrace:/APPLICATION-123456'
    }
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[expected_check_state],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})


@freeze_time('2025-07-22 08:26:24')
def test_error_event(dynatrace_check, test_instance, requests_mock, health, aggregator):
    event_type = "ERROR_EVENT"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_error.json', 'samples')
    set_http_responses(requests_mock, error_event=event_type_response)
    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    expected_check_state = {
        'checkStateId': 'SERVICE-654321', 'health': 'DEVIATING', 'name': 'Dynatrace event',
        'message': 'Event: Error Event Severity: ERROR Impact: SERVICE Open Since: '
                   'Mar 15, 2023, 13:50:00 Source: builtin',
        'topologyElementIdentifier': 'urn:dynatrace:/SERVICE-654321'
    }
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[expected_check_state],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})


@freeze_time('2025-07-22 08:26:24')
def test_performance_event(dynatrace_check, test_instance, requests_mock, health, aggregator):
    event_type = "PERFORMANCE_EVENT"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_performance.json', 'samples')
    set_http_responses(requests_mock, performance_event=event_type_response)
    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream, check_states=[],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})


@freeze_time('2025-07-22 08:26:24')
def test_resource_contention_event(dynatrace_check, test_instance, requests_mock, health, aggregator):
    event_type = "RESOURCE_CONTENTION"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_resource_contention.json', 'samples')
    set_http_responses(requests_mock, resource_contention_event=event_type_response)
    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    expected_check_state = {
        'checkStateId': 'HOST-ABCDEF', 'health': 'DEVIATING', 'name': 'Dynatrace event',
        'message': 'Event: Resource Contention Event Severity: RESOURCE_CONTENTION Impact: INFRASTRUCTURE Open Since: '
                   'Mar 15, 2023, 14:20:00 Source: builtin',
        'topologyElementIdentifier': 'urn:dynatrace:/HOST-ABCDEF'
    }
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[expected_check_state],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})


@freeze_time('2025-07-22 08:26:24')
def test_custom_deployment_event(dynatrace_check, test_instance, requests_mock, health, aggregator, telemetry):
    event_type = "CUSTOM_DEPLOYMENT"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_custom_deployment.json', 'samples')
    set_http_responses(requests_mock, custom_deployment_event=event_type_response)

    entity_id = event['entityId']['entityId']['id']
    entity_name = event['entityId']['name']
    requests_mock.get(f"{test_instance['url']}/api/v2/entities/{entity_id}",
                      text=json.dumps({"displayName": entity_name}))

    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream, check_states=[],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})
    assert len(telemetry._topology_events) == 1
    assert telemetry._topology_events[0]['msg_title'] == "Custom Deployment on Frontend App"


@freeze_time('2025-07-22 08:26:24')
def test_custom_annotation_event(dynatrace_check, test_instance, requests_mock, health, aggregator, telemetry):
    event_type = "CUSTOM_ANNOTATION"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_custom_annotation.json', 'samples')
    set_http_responses(requests_mock, custom_annotation_event=event_type_response)

    entity_id = event['entityId']['entityId']['id']
    entity_name = event['entityId']['name']
    requests_mock.get(f"{test_instance['url']}/api/v2/entities/{entity_id}",
                      text=json.dumps({"displayName": entity_name}))

    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream, check_states=[],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})
    assert len(telemetry._topology_events) == 1
    assert telemetry._topology_events[0]['msg_title'] == "Custom Annotation on User Database"


@freeze_time('2025-07-22 08:26:24')
def test_custom_info_event(dynatrace_check, test_instance, requests_mock, health, aggregator, telemetry):
    event_type = "CUSTOM_INFO"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_custom_info.json', 'samples')
    set_http_responses(requests_mock, custom_info_event=event_type_response)

    entity_id = event['entityId']['entityId']['id']
    entity_name = event['entityId']['name']
    requests_mock.get(f"{test_instance['url']}/api/v2/entities/{entity_id}",
                      text=json.dumps({"displayName": entity_name}))

    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream, check_states=[],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})
    assert len(telemetry._topology_events) == 1
    assert telemetry._topology_events[0]['msg_title'] == "Custom Info on Mobile App"


@freeze_time('2025-07-22 08:26:24')
def test_marked_for_termination_event(dynatrace_check, test_instance, requests_mock, health, aggregator, telemetry):
    event_type = "MARKED_FOR_TERMINATION"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_marked_for_termination.json', 'samples')
    set_http_responses(requests_mock, marked_for_termination_event=event_type_response)

    entity_id = event['entityId']['entityId']['id']
    entity_name = event['entityId']['name']
    requests_mock.get(f"{test_instance['url']}/api/v2/entities/{entity_id}",
                      text=json.dumps({"displayName": entity_name}))

    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    assert len(telemetry._topology_events) == 1
    assert telemetry._topology_events[0]['msg_title'] == "Marked for Termination on old-worker-5"


@freeze_time('2025-07-22 08:26:24')
def test_custom_alert_event(dynatrace_check, test_instance, requests_mock, health, aggregator):
    event_type = "CUSTOM_ALERT"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_custom_alert.json', 'samples')
    set_http_responses(requests_mock, custom_alert_event=event_type_response)
    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    expected_check_state = {
        'checkStateId': 'CUSTOM_DEVICE-EXT', 'health': 'DEVIATING', 'name': 'Dynatrace event',
        'message': 'Event: Custom Alert Severity: ERROR Impact: Unspecified Open Since: '
                   'Mar 15, 2023, 14:40:00 Source: External Monitoring',
        'topologyElementIdentifier': 'urn:dynatrace:/CUSTOM_DEVICE-EXT'
    }
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[expected_check_state],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})


@freeze_time('2025-07-22 08:26:24')
def test_custom_configuration_event(dynatrace_check, test_instance, requests_mock, health, aggregator, telemetry):
    event_type = "CUSTOM_CONFIGURATION"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_custom_configuration.json', 'samples')
    set_http_responses(requests_mock, custom_configuration_event=event_type_response)

    entity_id = event['entityId']['entityId']['id']
    entity_name = event['entityId']['name']
    requests_mock.get(f"{test_instance['url']}/api/v2/entities/{entity_id}",
                      text=json.dumps({"displayName": entity_name}))

    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream, check_states=[],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15}, stop_snapshot={})
    assert len(telemetry._topology_events) == 1
    assert telemetry._topology_events[0]['msg_title'] == "Custom Configuration on Configuration Service"


@freeze_time('2025-07-22 08:26:24')
def test_no_events_means_empty_health_snapshot(dynatrace_check, test_instance, requests_mock, health, aggregator):
    """
    Dynatrace health check should not produce any health states when there are no events
    """
    _mock_events_endpoint(requests_mock, test_instance,
                          read_file('no_events_response_v2.json', 'samples'), status_code=200)
    assert dynatrace_check.run() == ""
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                           stop_snapshot={})
    assert len(aggregator.events) == 0


@freeze_time('2021-02-16 14:26:24')
def test_raise_exception_for_response_code_not_200(dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Test to raise a check exception when API endpoint when status code is not 200
    """
    error_response = '{"error": {"code": 500, "message": "Simulated error!"}}'
    _mock_events_endpoint(requests_mock, test_instance, error_response, status_code=500)
    dynatrace_check.run()
    error_message = 'Got an unexpected error with status code 500 and message: Simulated error!'
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL,
                                    message=error_message)
    assert len(aggregator.events) == 0


@freeze_time('2021-02-16 14:26:24')
def test_timeout(dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Gracefully handle requests timeout exception
    """
    events_url_pattern = re.compile(r'{}/api/v2/events\?from=\d+'.format(re.escape(test_instance['url'])))
    requests_mock.get(events_url_pattern, exc=requests.exceptions.ConnectTimeout)
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL,
                                    message='Timeout exception occurred for endpoint '
                                            'https://instance.live.dynatrace.com/api/v2/events with message: '
                                            '20 seconds timeout')


def test_link_to_dynatrace(dynatrace_check, test_instance):
    url = test_instance['url']

    service_url = dynatrace_check.link_to_dynatrace("SERVICE-123", url)
    assert service_url == f"{url}/api/v2/entities/SERVICE-123"

    process_group_url = dynatrace_check.link_to_dynatrace("PROCESS_GROUP-456", url)
    assert process_group_url == f"{url}/api/v2/entities/PROCESS_GROUP-456"

    process_url = dynatrace_check.link_to_dynatrace("PROCESS-789", url)
    assert process_url == f"{url}/api/v2/entities/PROCESS-789"

    process_url = dynatrace_check.link_to_dynatrace("PROCESS_GROUP_INSTANCE-000", url)
    assert process_url == f"{url}/api/v2/entities/PROCESS_GROUP_INSTANCE-000"

    host_url = dynatrace_check.link_to_dynatrace("HOST-abc", url)
    assert host_url == f"{url}/api/v2/entities/HOST-abc"

    application_url = dynatrace_check.link_to_dynatrace("APPLICATION-def", url)
    assert application_url == f"{url}/api/v2/entities/APPLICATION-def"

    custom_device_url = dynatrace_check.link_to_dynatrace("CUSTOM_DEVICE-abc", url)
    assert custom_device_url == f"{url}/api/v2/entities/CUSTOM_DEVICE-abc"


def test_link_to_dynatrace_unknown_type(dynatrace_check, test_instance):
    instance_url = test_instance.get('url')
    process_url = dynatrace_check.link_to_dynatrace('UNKNOWN', instance_url)
    assert process_url == instance_url


@freeze_time('2025-07-22 08:26:24')
def test_events_process_limit(dynatrace_check, test_instance, requests_mock, health, aggregator):
    """
    Check should respect `events_process_limit` config setting and just produce those number of events.
    """
    event_type_response_fri = read_file('event_type_failure_rate_increased.json', 'samples')
    event_type_response_pr = read_file('event_type_process_restart.json', 'samples')
    event_type_response_dcc = read_file('event_type_deployment_changed_change.json', 'samples')
    set_http_responses(requests_mock, failure_rate_increased_event=event_type_response_fri,
                       process_restart_event=event_type_response_pr,
                       deployment_changed_change_event=event_type_response_dcc)

    events_response = json.loads(read_file('11_events_response.json', 'samples'))
    for event in events_response['events']:
        if event['eventType'] in ["PROCESS_RESTART", "DEPLOYMENT_CHANGED_CHANGE"]:
            entity_id = event['entityId']['entityId']['id']
            entity_name = event['entityId']['name']
            requests_mock.get(f"{test_instance['url']}/api/v2/entities/{entity_id}",
                              text=json.dumps({"displayName": entity_name}))

    _mock_events_endpoint(requests_mock, test_instance, events_response, status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.WARNING,
                                    message='Maximum event limit to process is 10 but received total 11 events')

    # 2 open events were in the first 10 events processed, so we expect 2 health states
    health.assert_snapshot(
        dynatrace_check.check_id,
        dynatrace_check.health.stream,
        check_states=[
            {
                'checkStateId': 'SERVICE-FAA29C9BB1C02F9B',
                'health': 'DEVIATING',
                'name': 'Dynatrace event',
                'message': 'Event: Failure Rate Increased Severity: ERROR Impact: SERVICE Open Since: '
                           'Jun 23, 2025, 03:43:20 Source: builtin',
                'topologyElementIdentifier': 'urn:dynatrace:/SERVICE-FAA29C9BB1C02F9B'
            },
            {
                'checkStateId': 'SERVICE-9B16B9C5B03836C5',
                'health': 'DEVIATING',
                'name': 'Dynatrace event',
                'message': 'Event: Failure Rate Increased Severity: ERROR Impact: SERVICE Open Since: '
                           'Jun 23, 2025, 04:23:20 Source: builtin',
                'topologyElementIdentifier': 'urn:dynatrace:/SERVICE-9B16B9C5B03836C5'
            }
        ],
        start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
        stop_snapshot={}
    )


@freeze_time('2025-07-22 08:26:24')
def test_events_process_limit_with_batches(dynatrace_check, test_instance, requests_mock, health, aggregator):
    """
    Check should respect `events_process_limit` config setting with batch event retrieval.
    """
    event_type_response = read_file('event_type_failure_rate_increased.json', 'samples')
    event_type_response_pr = read_file('event_type_process_restart.json', 'samples')
    set_http_responses(requests_mock, failure_rate_increased_event=event_type_response,
                       process_restart_event=event_type_response_pr)

    events_batch_1 = json.loads(read_file('events_batch_1.json', 'samples'))
    for event in events_batch_1['events']:
        if event['eventType'] == "PROCESS_RESTART":
            entity_id = event['entityId']['entityId']['id']
            entity_name = event['entityId']['name']
            requests_mock.get(f"{test_instance['url']}/api/v2/entities/{entity_id}",
                              text=json.dumps({"displayName": entity_name}))

    _mock_events_endpoint(requests_mock, test_instance, events_batch_1, status_code=200)
    requests_mock.get(f"{test_instance['url']}/api/v2/events?nextPageKey=nextPageKey_mock_123", status_code=200,
                      text=read_file('events_batch_2.json', 'samples'))

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.WARNING,
                                    message='Maximum event limit to process is 10 but received total 11 events')

    # Only 1 open event was in the first 10 events processed, so we expect 1 health state
    health.assert_snapshot(
        dynatrace_check.check_id,
        dynatrace_check.health.stream,
        check_states=[
            {
                'checkStateId': 'SERVICE-BATCH-1',
                'health': 'DEVIATING',
                'name': 'Dynatrace event',
                'message': 'Event: Failure Rate Increased Severity: ERROR Impact: SERVICE Open Since: '
                           'Jun 23, 2025, 03:43:20 Source: builtin',
                'topologyElementIdentifier': 'urn:dynatrace:/SERVICE-BATCH-1'
            }
        ],
        start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
        stop_snapshot={}
    )


@freeze_time('2025-07-22 08:26:24')
def test_unicode_in_response_text(dynatrace_check, test_instance, requests_mock, aggregator, telemetry):
    """
    Check should correctly handle unicode characters in the API response.
    """
    event_type_response = read_file('event_type_process_restart.json', 'samples')
    set_http_responses(requests_mock, process_restart_event=event_type_response)

    event = json.loads(read_file('unicode_event_response.json', 'samples'))
    entity_id = event['events'][0]['entityId']['entityId']['id']
    entity_name = event['events'][0]['entityId']['name']
    requests_mock.get(f"{test_instance['url']}/api/v2/entities/{entity_id}",
                      text=json.dumps({"displayName": entity_name}))

    _mock_events_endpoint(requests_mock, test_instance,
                          read_file('unicode_event_response.json', 'samples'), status_code=200)

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    assert len(telemetry._topology_events) == 1
    assert telemetry._topology_events[0]['msg_title'] == "Process Restart on aws-cni™"


@freeze_time('2025-07-22 08:26:24')
def test_checks_in_flight_normal_execution(dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Test that checks_in_flight is properly incremented at start and decremented at end
    during normal execution.
    """
    os.environ["JWT_AUTH"] = "false"

    # Mock empty events response
    event_response = {"totalCount": 0, "pageSize": 0, "events": []}
    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    # Run the check - should succeed
    dynatrace_check.run()

    # Verify service check is OK
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)

    # Verify checks_in_flight was incremented then decremented (should be 0 at end)
    final_state = dynatrace_check.state_manager.get_state(dynatrace_check._get_state_descriptor())
    assert final_state is not None
    assert final_state['checks_in_flight'] == 0


@freeze_time('2025-07-22 08:26:24')
def test_checks_in_flight_blocks_concurrent_execution(dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Test that a second check is prevented from starting if checks_in_flight > 0.
    """
    os.environ["JWT_AUTH"] = "false"

    # Set initial state with checks_in_flight = 1 (simulating a running check)
    initial_state = {
        'last_processed_event_timestamp': 1721636784000,
        'checks_in_flight': 1
    }
    state_descriptor = dynatrace_check._get_state_descriptor()
    dynatrace_check.state_manager.set_state(state_descriptor, initial_state)

    # Mock empty events response (won't be called because check exits early)
    event_response = {"totalCount": 0, "pageSize": 0, "events": []}
    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    # Run the check - should exit early with WARNING
    dynatrace_check.run()

    # Verify service check is WARNING (not OK)
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.WARNING)

    # Verify checks_in_flight remains 1 (wasn't modified because check exited)
    final_state = dynatrace_check.state_manager.get_state(state_descriptor)
    assert final_state is not None
    assert final_state['checks_in_flight'] == 1


@freeze_time('2025-07-22 08:26:24')
def test_checks_in_flight_exception_recovery(dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Test that checks_in_flight is decremented on exception and the next check can start.
    """
    os.environ["JWT_AUTH"] = "false"

    # Mock to raise an exception during event processing
    _mock_events_endpoint(requests_mock, test_instance, "Internal Server Error", status_code=500)

    # First run - should fail with exception
    dynatrace_check.run()

    # Verify service check is CRITICAL
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL)

    # Verify checks_in_flight was decremented to 0 despite exception
    state_descriptor = dynatrace_check._get_state_descriptor()
    state_after_exception = dynatrace_check.state_manager.get_state(state_descriptor)
    assert state_after_exception is not None
    assert state_after_exception['checks_in_flight'] == 0

    # Reset aggregator for second run
    aggregator.reset()

    # Mock successful response for second run
    event_response = {"totalCount": 0, "pageSize": 0, "events": []}
    _mock_events_endpoint(requests_mock, test_instance, event_response)

    # Second run - should succeed because checks_in_flight is 0
    dynatrace_check.run()

    # Verify service check is OK
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)

    # Verify checks_in_flight is still 0
    final_state = dynatrace_check.state_manager.get_state(state_descriptor)
    assert final_state is not None
    assert final_state['checks_in_flight'] == 0


@freeze_time('2025-07-22 08:26:24')
def test_checks_in_flight_with_event_limit_exception(dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Test that checks_in_flight is decremented when EventLimitReachedException is raised.
    """
    os.environ["JWT_AUTH"] = "false"

    # Create response with more events than the limit (10)
    events = []
    for i in range(15):
        events.append({
            "eventId": f"event-{i}",
            "startTime": 1750649000000 + (i * 1000),
            "eventType": "PROCESS_RESTART",
            "status": "CLOSED",
            "properties": [],
            "title": f"process-{i}",
            "entityId": {
                "entityId": {"id": f"PGI-{i}", "type": "PROCESS_GROUP_INSTANCE"},
                "name": f"process-{i}"
            },
            "correlationId": "",
            "entityTags": [],
            "managementZones": [],
            "underMaintenance": False,
            "suppressAlert": False,
            "suppressProblem": False,
            "frequentEvent": False,
            "endTime": 0
        })

    event_response = {"totalCount": 15, "pageSize": 15, "events": events}
    event_type_response = read_file('event_type_process_restart.json', 'samples')
    set_http_responses(requests_mock, process_restart_event=event_type_response)

    _mock_events_endpoint(requests_mock, test_instance, event_response, status_code=200)

    # Run check - should hit event limit and raise EventLimitReachedException
    dynatrace_check.run()

    # Verify service check is WARNING (EventLimitReachedException)
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.WARNING)

    # Verify checks_in_flight was decremented to 0 despite exception
    final_state = dynatrace_check.state_manager.get_state(dynatrace_check._get_state_descriptor())
    assert final_state is not None
    assert final_state['checks_in_flight'] == 0


# Cache Warming Tests
@freeze_time('2025-07-22 08:26:24')
def test_is_warmup_enabled_default_false(dynatrace_check):
    """
    Test that _is_warmup_enabled() returns False by default when env var is not set
    """
    # Ensure env var is not set
    if 'DYNATRACE_HEALTH_ENABLE_WARMUP' in os.environ:
        del os.environ['DYNATRACE_HEALTH_ENABLE_WARMUP']

    assert dynatrace_check._is_warmup_enabled() is False


@freeze_time('2025-07-22 08:26:24')
def test_is_warmup_enabled_case_insensitive(dynatrace_check):
    """
    Test that _is_warmup_enabled() is case insensitive for various true values
    """
    test_values = ['true', 'True', 'TRUE', 'TrUe', 'tRuE']

    for value in test_values:
        os.environ['DYNATRACE_HEALTH_ENABLE_WARMUP'] = value
        assert dynatrace_check._is_warmup_enabled() is True, f"Failed for value: {value}"

    # Test false values
    false_values = ['false', 'False', 'FALSE', 'anything_else', '1', '0']
    for value in false_values:
        os.environ['DYNATRACE_HEALTH_ENABLE_WARMUP'] = value
        assert dynatrace_check._is_warmup_enabled() is False, f"Failed for value: {value}"


@freeze_time('2025-07-22 08:26:24')
def test_cache_warming_enabled_executes(dynatrace_check, test_instance, requests_mock, aggregator, mocker):
    """
    Test that cache warming methods are called when DYNATRACE_HEALTH_ENABLE_WARMUP=true
    """
    os.environ["JWT_AUTH"] = "false"
    os.environ['DYNATRACE_HEALTH_ENABLE_WARMUP'] = 'true'

    # Mock cache warming methods
    warm_event_type_cache_mock = mocker.patch.object(dynatrace_check, '_warm_event_type_cache')
    warm_all_supported_entities_mock = mocker.patch.object(dynatrace_check, '_warm_all_supported_entities')

    # Mock events response with some events to trigger cache warming
    event_response = {
        "totalCount": 2,
        "pageSize": 2,
        "events": [
            {
                "eventId": "event-1",
                "startTime": 1750649000000,
                "eventType": "PROCESS_RESTART",
                "status": "CLOSED",
                "properties": [],
                "title": "process-1",
                "entityId": {
                    "entityId": {"id": "PGI-1", "type": "PROCESS_GROUP_INSTANCE"},
                    "name": "process-1"
                },
                "correlationId": "",
                "entityTags": [],
                "managementZones": [],
                "underMaintenance": False,
                "suppressAlert": False,
                "suppressProblem": False,
                "frequentEvent": False,
                "endTime": 0
            },
            {
                "eventId": "event-2",
                "startTime": 1750649001000,
                "eventType": "ERROR_EVENT",
                "status": "CLOSED",
                "properties": [],
                "title": "error-1",
                "entityId": {
                    "entityId": {"id": "PGI-2", "type": "PROCESS_GROUP_INSTANCE"},
                    "name": "process-2"
                },
                "correlationId": "",
                "entityTags": [],
                "managementZones": [],
                "underMaintenance": False,
                "suppressAlert": False,
                "suppressProblem": False,
                "frequentEvent": False,
                "endTime": 0
            }
        ]
    }

    # Mock event type responses
    event_type_response = read_file('event_type_process_restart.json', 'samples')
    set_http_responses(requests_mock, process_restart_event=event_type_response)

    # Mock entities endpoint
    requests_mock.get(f"{test_instance['url']}/api/v2/entities?entitySelector=type(PROCESS_GROUP_INSTANCE)",
                      status_code=200, text='{"totalCount": 0, "entities": []}')
    requests_mock.get(f"{test_instance['url']}/api/v2/entities?entitySelector=type(HOST)",
                      status_code=200, text='{"totalCount": 0, "entities": []}')

    _mock_events_endpoint(requests_mock, test_instance, event_response)

    # Run the check
    dynatrace_check.run()

    # Verify cache warming methods were called
    warm_event_type_cache_mock.assert_called_once()
    warm_all_supported_entities_mock.assert_called_once()

    # Verify service check is OK
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)


@freeze_time('2025-07-22 08:26:24')
def test_cache_warming_disabled_skips(dynatrace_check, test_instance, requests_mock, aggregator, mocker):
    """
    Test that cache warming methods are NOT called when DYNATRACE_HEALTH_ENABLE_WARMUP=false
    """
    os.environ["JWT_AUTH"] = "false"
    os.environ['DYNATRACE_HEALTH_ENABLE_WARMUP'] = 'false'

    # Mock cache warming methods
    warm_event_type_cache_mock = mocker.patch.object(dynatrace_check, '_warm_event_type_cache')
    warm_all_supported_entities_mock = mocker.patch.object(dynatrace_check, '_warm_all_supported_entities')

    # Mock events response with some events
    event_response = {
        "totalCount": 1,
        "pageSize": 1,
        "events": [
            {
                "eventId": "event-1",
                "startTime": 1750649000000,
                "eventType": "PROCESS_RESTART",
                "status": "CLOSED",
                "properties": [],
                "title": "process-1",
                "entityId": {
                    "entityId": {"id": "PGI-1", "type": "PROCESS_GROUP_INSTANCE"},
                    "name": "process-1"
                },
                "correlationId": "",
                "entityTags": [],
                "managementZones": [],
                "underMaintenance": False,
                "suppressAlert": False,
                "suppressProblem": False,
                "frequentEvent": False,
                "endTime": 0
            }
        ]
    }

    event_type_response = read_file('event_type_process_restart.json', 'samples')
    set_http_responses(requests_mock, process_restart_event=event_type_response)

    _mock_events_endpoint(requests_mock, test_instance, event_response)

    # Run the check
    dynatrace_check.run()

    # Verify cache warming methods were NOT called
    warm_event_type_cache_mock.assert_not_called()
    warm_all_supported_entities_mock.assert_not_called()

    # Verify service check is OK
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)


@freeze_time('2025-07-22 08:26:24')
def test_cache_warming_exception_handling(dynatrace_check, test_instance, requests_mock, aggregator, mocker):
    """
    Test that cache warming exceptions don't break the main check logic
    """
    os.environ["JWT_AUTH"] = "false"
    os.environ['DYNATRACE_HEALTH_ENABLE_WARMUP'] = 'true'

    # Mock cache warming methods to raise exceptions
    mocker.patch.object(dynatrace_check, '_warm_event_type_cache', side_effect=Exception("Event type warming failed"))
    mocker.patch.object(dynatrace_check, '_warm_all_supported_entities', side_effect=Exception("Entity warming failed"))

    # Mock events response
    event_response = {"totalCount": 0, "pageSize": 0, "events": []}
    _mock_events_endpoint(requests_mock, test_instance, event_response)

    # Run the check - should not raise exception despite cache warming failures
    dynatrace_check.run()

    # Verify service check is still OK despite cache warming failures
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)


@freeze_time('2025-07-22 08:26:24')
def test_cache_warming_with_no_events(dynatrace_check, test_instance, requests_mock, aggregator, mocker):
    """
    Test cache warming behavior when there are no events to process
    """
    os.environ["JWT_AUTH"] = "false"
    os.environ['DYNATRACE_HEALTH_ENABLE_WARMUP'] = 'true'

    # Mock cache warming methods
    warm_event_type_cache_mock = mocker.patch.object(dynatrace_check, '_warm_event_type_cache')
    warm_all_supported_entities_mock = mocker.patch.object(dynatrace_check, '_warm_all_supported_entities')

    # Mock empty events response
    event_response = {"totalCount": 0, "pageSize": 0, "events": []}
    _mock_events_endpoint(requests_mock, test_instance, event_response)

    # Mock entities endpoint for entity warming
    requests_mock.get(f"{test_instance['url']}/api/v2/entities?entitySelector=type(PROCESS_GROUP_INSTANCE)",
                      status_code=200, text='{"totalCount": 0, "entities": []}')
    requests_mock.get(f"{test_instance['url']}/api/v2/entities?entitySelector=type(HOST)",
                      status_code=200, text='{"totalCount": 0, "entities": []}')

    # Run the check
    dynatrace_check.run()

    # Verify event type cache warming was called with empty set (no unique event types)
    warm_event_type_cache_mock.assert_called_once()
    args, kwargs = warm_event_type_cache_mock.call_args
    assert args[2] == set()  # unique_event_types should be empty set

    # Verify entity cache warming was still called
    warm_all_supported_entities_mock.assert_called_once()

    # Verify service check is OK
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
