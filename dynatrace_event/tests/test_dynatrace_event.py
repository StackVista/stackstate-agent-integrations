# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import os

import mock
import requests_mock

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.stubs import aggregator, telemetry
from stackstate_checks.dynatrace_event.dynatrace_event import generate_bootstrap_timestamp, State


def test_check_for_empty_events(check, instance):
    """
    Testing Dynatrace event check should not produce any events
    """
    with requests_mock.Mocker() as m:
        url = '{}/api/v1/events?from={}'.format(instance['url'], generate_bootstrap_timestamp(5))
        m.get(url, status_code=200, text=read_data_from_file('no_events.json'))
        check.run()
        service_checks = aggregator.service_checks('dynatrace_event')
        assert len(service_checks) == 1
        assert service_checks[0].status == AgentCheck.OK
        assert service_checks[0].message == 'Dynatrace events processed successfully'
        assert len(aggregator.events) == 0


def test_check_for_event_limit_reached_condition(check, instance):
    """
    Testing Dynatrace should throw `EventLimitReachedException` if the number of events
    between subsequent check runs exceed the `events_process_limit`
    """
    with requests_mock.Mocker() as m:
        url = '{}/api/v1/events?from={}'.format(instance['url'], generate_bootstrap_timestamp(5))
        m.get(url, status_code=200, text=read_data_from_file('21events.json'))
        check.run()
        service_checks = aggregator.service_checks('dynatrace_event')
        assert len(service_checks) == 1
        assert service_checks[0].status == AgentCheck.CRITICAL
        assert service_checks[0].message == 'Maximum event limit to process is 10 but received total 21 events'


def test_check_respects_events_process_limit_on_startup(check, instance):
    """
    Testing Dynatrace should respect `events_process_limit` config and just produce those number of events
    """
    with requests_mock.Mocker() as m:
        url1 = '{}/api/v1/events?from={}'.format(instance['url'], generate_bootstrap_timestamp(5))
        url2 = '{}/api/v1/events?cursor={}'.format(instance['url'], '123')
        url3 = '{}/api/v1/events?cursor={}'.format(instance['url'], '345')
        m.get(url1, status_code=200, text=read_data_from_file("events_set1.json"))
        m.get(url2, status_code=200, text=read_data_from_file("events_set2.json"))
        m.get(url3, status_code=200, text=read_data_from_file("events_set3.json"))
        check.run()
        service_checks = aggregator.service_checks('dynatrace_event')
        assert len(aggregator.events) == 12
        assert len(service_checks) == 1
        assert service_checks[0].status == AgentCheck.OK


def test_check_for_error_in_events(check):
    """
    Testing Dynatrace check should produce service check when error thrown
    """
    error_msg = "mocked test error occurred"
    check.get_dynatrace_event_json_response = mock.MagicMock(return_value={"error": {"message": error_msg}})
    check.run()
    service_checks = aggregator.service_checks('dynatrace_event')
    assert len(aggregator.events) == 0
    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL
    assert service_checks[0].message == 'Error in pulling the events: {}'.format(error_msg)


def test_check_raise_exception_for_response_code_not_200(check, instance):
    """
    Test to raise a check exception when API endpoint when status code is not 200
    """

    with requests_mock.Mocker() as m:
        url = '{}/api/v1/events?from={}'.format(instance['url'], generate_bootstrap_timestamp(5))
        m.get(url, status_code=500, text='error')
        check.run()
        service_checks = aggregator.service_checks('dynatrace_event')
        assert len(aggregator.events) == 0
        assert len(service_checks) == 1
        assert service_checks[0].status == AgentCheck.CRITICAL
        assert service_checks[0].message == 'Got 500 when hitting https://instance.live.dynatrace.com/api/v1/events'


def test_check_raise_exception(check):
    """
    Test to raise a exception from code that talks to API endpoint throws exception
    """
    check.get_dynatrace_event_json_response = mock.MagicMock(side_effect=Exception("Mocked exception occurred"))
    check.run()
    service_checks = aggregator.service_checks("dynatrace_event")
    assert len(aggregator.events) == 0
    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL
    assert service_checks[0].message == 'Mocked exception occurred'


def test_check_for_generated_events(check, instance):
    """
    Testing Dynatrace check should produce full events
    """
    empty_state_timestamp = generate_bootstrap_timestamp(5)
    with requests_mock.Mocker() as m:
        url = '{}/api/v1/events?from={}'.format(instance['url'], empty_state_timestamp)
        m.get(url, status_code=200, text=read_data_from_file('9events.json'))
        check._current_time_seconds = mock.MagicMock(return_value=1613485584)
        check.run()
        service_checks = aggregator.service_checks("dynatrace_event")
        assert len(aggregator.events) == 8
        assert len(telemetry._topology_events) == 1
        assert len(service_checks) == 1
        assert service_checks[0].status == AgentCheck.OK
        processed_events = read_json_from_file('processed_events.json')
        for event in processed_events:
            aggregator.assert_event(event.get('msg_text'))
        processed_topology_events = read_json_from_file('processed_topology_events.json')
        for event in processed_topology_events:
            telemetry.assert_topology_event(event)


def read_data_from_file(filename):
    with open(get_path_to_file(filename), "r") as f:
        return f.read()


def read_json_from_file(filename):
    with open(get_path_to_file(filename), 'r') as f:
        return json.load(f)


def get_path_to_file(filename):
    path_to_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', filename)
    return path_to_file
