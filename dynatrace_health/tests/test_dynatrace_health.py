# -*- coding: utf-8 -*-

# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import requests
from freezegun import freeze_time

from stackstate_checks.base import AgentCheck, StateDescriptor
from stackstate_checks.base.utils.common import read_file, load_json_from_file
from stackstate_checks.dynatrace_health import State


@freeze_time('2021-02-16 14:26:24')
def test_no_events_means_empty_health_snapshot(dynatrace_check, test_instance, requests_mock, health, aggregator):
    """
    Dynatrace health check should not produce any health states when there are no events
    """
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v1/events?from={}'.format(test_instance['url'], timestamp), status_code=200,
                      text=read_file('no_events_response.json', 'samples'))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                           stop_snapshot={})
    assert len(aggregator.events) == 0


@freeze_time('2021-02-16 14:26:24')
def test_events_process_limit(dynatrace_check, test_instance, aggregator, requests_mock, health):
    """
    Check should respect `events_process_limit` config setting and just produce those number of events
    """
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v1/events?from={}'.format(test_instance['url'], timestamp), status_code=200,
                      text=read_file('21_events_response.json', 'samples'))
    dynatrace_check.run()
    # service check returns warning about events_process_limit
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.WARNING,
                                    message='Maximum event limit to process is 10 but received total 11 events')
    # 2 open events were in first 10 events gathered -> 2 health states
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[{'checkStateId': 'SERVICE-FAA29C9BB1C02F9B',
                                          'health': 'DEVIATING',
                                          'message': 'Event: FAILURE_RATE_INCREASED Severity: ERROR '
                                                     'Impact: SERVICE Open Since: 1600874700000 '
                                                     'Source: builtin',
                                          'name': 'Dynatrace event',
                                          'topologyElementIdentifier': 'urn:dynatrace:/SERVICE-FAA29C9BB1C02F9B'},
                                         {'checkStateId': 'SERVICE-9B16B9C5B03836C5',
                                          'health': 'DEVIATING',
                                          'message': 'Event: FAILURE_RATE_INCREASED Severity: ERROR '
                                                     'Impact: SERVICE Open Since: 1600874820000 '
                                                     'Source: builtin',
                                          'name': 'Dynatrace event',
                                          'topologyElementIdentifier': 'urn:dynatrace:/SERVICE-9B16B9C5B03836C5'}],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                           stop_snapshot={})


@freeze_time('2021-02-16 14:26:24')
def test_events_process_limit_with_batches(dynatrace_check, test_instance, requests_mock, aggregator, health):
    """
    Respecting `events_process_limit` config setting should happen with batch event retrieval too
    """
    url = test_instance['url']
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    # there are 3 batch calls with total 12 events, open events are 3rd and 12th in collection
    url1 = '{}/api/v1/events?from={}'.format(url, timestamp)
    url2 = '{}/api/v1/events?cursor={}'.format(url, '123')
    url3 = '{}/api/v1/events?cursor={}'.format(url, '345')
    requests_mock.get(url1, status_code=200, text=read_file('events_set1_response.json', 'samples'))
    requests_mock.get(url2, status_code=200, text=read_file('events_set2_response.json', 'samples'))
    requests_mock.get(url3, status_code=200, text=read_file('events_set3_response.json', 'samples'))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.WARNING,
                                    message='Maximum event limit to process is 10 but received total 11 events')
    # 1 open event were in first 10 events gathered -> 1 health states
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[{'checkStateId': 'SERVICE-FAA29C9BB1C02F9B',
                                          'health': 'DEVIATING',
                                          'message': 'Event: FAILURE_RATE_INCREASED Severity: ERROR '
                                                     'Impact: SERVICE Open Since: 1600874700000 '
                                                     'Source: builtin',
                                          'name': 'Dynatrace event',
                                          'topologyElementIdentifier': 'urn:dynatrace:/SERVICE-FAA29C9BB1C02F9B'}
                                         ],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                           stop_snapshot={})


@freeze_time('2021-02-16 14:26:24')
def test_raise_exception_for_response_code_not_200(dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Test to raise a check exception when API endpoint when status code is not 200
    """
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v1/events?from={}'.format(test_instance['url'], timestamp),
                      status_code=500, text='{"error": {"code": 500, "message": "Simulated error!"}}')
    dynatrace_check.run()
    error_message = 'Got an unexpected error with status code 500 and message: Simulated error!'
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL,
                                    message=error_message)
    assert len(aggregator.events) == 0


@freeze_time('2021-02-16 14:26:24')
def test_generated_events(dynatrace_check, test_instance, requests_mock, aggregator, telemetry, health):
    """
    Testing Dynatrace check should produce full events
    """
    url = test_instance['url']
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v1/events?from={}'.format(url, timestamp), status_code=200,
                      text=read_file('9_events_response.json', 'samples'))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[{'checkStateId': 'HOST-1E81568BDBFFE7FC',
                                          'health': 'DEVIATING',
                                          'message': 'Event: CPU_SATURATED Severity: '
                                                     'RESOURCE_CONTENTION Impact: INFRASTRUCTURE Open '
                                                     'Since: 1613466660000 Source: builtin',
                                          'name': 'Dynatrace event',
                                          'topologyElementIdentifier': 'urn:dynatrace:/HOST-1E81568BDBFFE7FC'},
                                         {'checkStateId': 'HOST-AA7D1491C9FE6BC4',
                                          'health': 'CRITICAL',
                                          'message': 'Event: CONNECTION_LOST Severity: AVAILABILITY '
                                                     'Impact: INFRASTRUCTURE Open Since: '
                                                     '1613430060468 Source: builtin',
                                          'name': 'Dynatrace event',
                                          'topologyElementIdentifier': 'urn:dynatrace:/HOST-AA7D1491C9FE6BC4'},
                                         {'checkStateId': 'HOST-8F3EDA24EEF51137',
                                          'health': 'CRITICAL',
                                          'message': 'Event: CONNECTION_LOST Severity: AVAILABILITY '
                                                     'Impact: INFRASTRUCTURE Open Since: '
                                                     '1613430060467 Source: builtin',
                                          'name': 'Dynatrace event',
                                          'topologyElementIdentifier': 'urn:dynatrace:/HOST-8F3EDA24EEF51137'}],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                           stop_snapshot={})
    assert len(telemetry._topology_events) == 1
    expected_topology_events = load_json_from_file('expected_topology_events.json', 'samples')
    for expected_event in expected_topology_events:
        assert expected_event == telemetry._topology_events[0]


@freeze_time('2021-02-16 14:26:24')
def test_state_data(state, dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Check is the right timestamp is writen to the state
    """
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    state_instance = StateDescriptor("instance.dynatrace_health.https_instance.live.dynatrace.com", "dynatrace.d")
    state.assert_state(state_instance, None)
    events_file = 'no_events_response.json'
    requests_mock.get('{}/api/v1/events?from={}'.format(test_instance['url'], timestamp), status_code=200,
                      text=read_file(events_file, 'samples'))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    mocked_response_data = load_json_from_file(events_file, 'samples')
    new_state = State({'last_processed_event_timestamp': mocked_response_data.get('to')})
    state.assert_state(state_instance, new_state)


@freeze_time('2021-02-16 14:26:24')
def test_timeout(dynatrace_check, test_instance, requests_mock, aggregator):
    """
    Gracefully handle requests timeout exception
    """
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v1/events?from={}'.format(test_instance['url'], timestamp),
                      exc=requests.exceptions.ConnectTimeout)
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.CRITICAL,
                                    message='Timeout exception occurred for endpoint '
                                            'https://instance.live.dynatrace.com/api/v1/events with message: '
                                            '20 seconds timeout')


def test_link_to_dynatrace(dynatrace_check, test_instance):
    url = test_instance['url']

    service_url = dynatrace_check.link_to_dynatrace("SERVICE-123", url)
    assert service_url == "https://instance.live.dynatrace.com/#newservices/serviceOverview;id=SERVICE-123"

    process_group_url = dynatrace_check.link_to_dynatrace("PROCESS_GROUP-456", url)
    assert process_group_url == "https://instance.live.dynatrace.com/#processgroupdetails;id=PROCESS_GROUP-456"

    process_url = dynatrace_check.link_to_dynatrace("PROCESS-789", url)
    assert process_url == "https://instance.live.dynatrace.com/#processdetails;id=PROCESS-789"

    process_url = dynatrace_check.link_to_dynatrace("PROCESS_GROUP_INSTANCE-000", url)
    assert process_url == "https://instance.live.dynatrace.com/#processdetails;id=PROCESS_GROUP_INSTANCE-000"

    host_url = dynatrace_check.link_to_dynatrace("HOST-abc", url)
    assert host_url == "https://instance.live.dynatrace.com/#newhosts/hostdetails;id=HOST-abc"

    application_url = dynatrace_check.link_to_dynatrace("APPLICATION-def", url)
    assert application_url == "https://instance.live.dynatrace.com/#uemapplications/uemappmetrics;uemapplicationId=" \
                              "APPLICATION-def"

    custom_device_url = dynatrace_check.link_to_dynatrace("CUSTOM_DEVICE-abc", url)
    assert custom_device_url == 'https://instance.live.dynatrace.com/#customdevicegroupdetails/entity;id=' \
                                'CUSTOM_DEVICE-abc'


def test_link_to_dynatrace_unknown_type(dynatrace_check, test_instance):
    instance_url = test_instance.get('url')
    process_url = dynatrace_check.link_to_dynatrace('UNKNOWN', instance_url)
    assert process_url == instance_url


@freeze_time('2021-02-16 14:26:24')
def test_unicode_in_response_text(dynatrace_check, test_instance, requests_mock, aggregator, telemetry):
    timestamp = dynatrace_check.generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    requests_mock.get('{}/api/v1/events?from={}'.format(test_instance['url'], timestamp), status_code=200,
                      text=read_file('unicode_topology_event_response.json', 'samples'))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    assert telemetry._topology_events[0]['msg_text'] == 'PROCESS_RESTART on aws-cni™'
