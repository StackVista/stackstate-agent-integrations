# -*- coding: utf-8 -*-

# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
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


@freeze_time('2025-07-22 08:26:24')
def test_availability_event(dynatrace_check, test_instance, requests_mock, health, aggregator):
    event_type = "AVAILABILITY_EVENT"
    event = _get_varied_event_by_type(event_type)
    event_response = {"totalCount": 1, "pageSize": 1, "events": [event]}
    event_type_response = read_file('event_type_availability.json', 'samples')
    set_http_responses(requests_mock, availability_event=event_type_response)
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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

    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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

    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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

    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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

    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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

    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(event_response))

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
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v2/events?from={}'.format(test_instance['url'], timestamp), status_code=200,
                      text=read_file('no_events_response_v2.json', 'samples'))
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
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v2/events?from={}'.format(test_instance['url'], timestamp),
                      status_code=500, text='{"error": {"code": 500, "message": "Simulated error!"}}')
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
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v2/events?from={}'.format(test_instance['url'], timestamp),
                      exc=requests.exceptions.ConnectTimeout)
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

    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(events_response))

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

    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=json.dumps(events_batch_1))
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

    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get(f"{test_instance['url']}/api/v2/events?from={timestamp}", status_code=200,
                      text=read_file('unicode_event_response.json', 'samples'))

    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    assert len(telemetry._topology_events) == 1
    assert telemetry._topology_events[0]['msg_title'] == "Process Restart on aws-cni™"
