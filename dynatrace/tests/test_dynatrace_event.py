# -*- coding: utf-8 -*-

# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import mock
import pytest
import requests
import requests_mock

from stackstate_checks.base import AgentCheck, StateDescriptor
from stackstate_checks.base.stubs import aggregator, telemetry, topology
from stackstate_checks.dynatrace.dynatrace import State, dynatrace_entities_cache
from .helpers import read_file, load_json_from_file

CHECK_NAME = 'dynatrace'


def test_no_events(dynatrace_check, test_instance):
    """
    Testing Dynatrace event check should not produce any events
    """
    dynatrace_check._process_topology = mock.MagicMock(return_value=None)
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        m.get('{}/api/v1/events?from={}'.format(url, timestamp), status_code=200,
              text=read_file('no_events_response.json'))
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.OK)
        assert len(aggregator.events) == 0


def test_events_process_limit(dynatrace_check, test_instance):
    """
    Check should respect `events_process_limit` config setting and just produce those number of events
    """
    dynatrace_check._process_topology = mock.MagicMock(return_value=None)
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        m.get('{}/api/v1/events?from={}'.format(url, timestamp), status_code=200,
              text=read_file('21_events_response.json'))
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.WARNING)
        assert len(aggregator.events) == test_instance.get("events_process_limit")


def test_events_process_limit_with_batches(dynatrace_check, test_instance):
    """
    Respecting `events_process_limit` config setting should happen with batch event retrieval too
    """
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    dynatrace_check._process_topology = mock.MagicMock(return_value=None)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        url1 = '{}/api/v1/events?from={}'.format(url, timestamp)
        url2 = '{}/api/v1/events?cursor={}'.format(url, '123')
        url3 = '{}/api/v1/events?cursor={}'.format(url, '345')
        m.get(url1, status_code=200, text=read_file("events_set1_response.json"))
        m.get(url2, status_code=200, text=read_file("events_set2_response.json"))
        m.get(url3, status_code=200, text=read_file("events_set3_response.json"))
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.WARNING)
        assert len(aggregator.events) == test_instance.get("events_process_limit")


def test_raise_exception_for_response_code_not_200(dynatrace_check, test_instance):
    """
    Test to raise a check exception when API endpoint when status code is not 200
    """
    dynatrace_check._process_topology = mock.MagicMock(return_value=None)
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        m.get('{}/api/v1/events?from={}'.format(url, timestamp),
              status_code=500, text='{"error": {"code": 500, "message": "Simulated error!"}}')
        dynatrace_check.run()
        error_message = 'Got an unexpected error with status code 500 and message: Simulated error!'
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.CRITICAL, message=error_message)
        assert len(aggregator.events) == 0


@pytest.mark.skip(reason='TODO rewrite to DynatraceClient test')
def test_exception_is_propagated_to_service_check(dynatrace_check):
    """
    Test to raise a exception from code that talks to API endpoint throws exception
    """
    dynatrace_check.get_dynatrace_json_response = mock.MagicMock(
        side_effect=Exception("Mocked exception occurred"))
    dynatrace_check._process_topology = mock.MagicMock(return_value=None)
    dynatrace_check.run()
    assert len(aggregator.events) == 0
    aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.CRITICAL,
                                    message='Mocked exception occurred')


def test_generated_events(dynatrace_check, test_instance):
    """
    Testing Dynatrace check should produce full events
    """
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    dynatrace_check._process_topology = mock.MagicMock(return_value=None)
    dynatrace_check._timestamp_to_sts_datetime = mock.MagicMock(return_value='Feb 15, 2021, 22:26:00')
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        m.get('{}/api/v1/events?from={}'.format(url, timestamp), status_code=200,
              text=read_file('9_events_response.json'))
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.OK)
        assert len(aggregator.events) == 8
        assert len(telemetry._topology_events) == 1
        expected_events = load_json_from_file('expected_events.json')
        for expected_event in expected_events:
            aggregator.assert_event(expected_event.get('msg_text'))
        expected_topology_events = load_json_from_file('expected_topology_events.json')
        for expected_event in expected_topology_events:
            # telemetry.assert_topology_event(expected_event)
            assert expected_event == telemetry._topology_events[0]


def test_state_data(state, dynatrace_check, test_instance):
    """
    Check is the right timestamp is writen to the state
    """
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    dynatrace_check._process_topology = mock.MagicMock(return_value=None)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    state_instance = StateDescriptor("instance.dynatrace_event.https_instance.live.dynatrace.com", "dynatrace_event.d")
    state.assert_state(state_instance, None)
    events_file = 'no_events_response.json'
    with requests_mock.Mocker() as m:
        m.get('{}/api/v1/events?from={}'.format(url, timestamp), status_code=200, text=read_file(events_file))
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.OK)
    mocked_response_data = load_json_from_file(events_file)
    new_state = State({'last_processed_event_timestamp': mocked_response_data.get('to')})
    state.assert_state(state_instance, new_state)


def test_timeout(dynatrace_check, test_instance):
    """
    Gracefully handle requests timeout exception
    """
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    dynatrace_check._process_topology = mock.MagicMock(return_value=None)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        m.get('{}/api/v1/events?from={}'.format(url, timestamp), exc=requests.exceptions.ConnectTimeout)
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.CRITICAL,
                                        message='Timeout exception occurred for endpoint '
                                                'https://instance.live.dynatrace.com/api/v1/events with message: '
                                                '20 seconds timeout')


def test_simulated_ok_events(dynatrace_check, test_instance):
    """
    Test if there is correct number of simulated events created
    """
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        m.get("{}/api/v1/entity/infrastructure/hosts".format(url), status_code=200,
              text=read_file('host_response.json'))
        m.get("{}/api/v1/entity/applications".format(url), status_code=200,
              text=read_file('application_response.json'))
        m.get("{}/api/v1/entity/services".format(url), status_code=200,
              text=read_file('service_response.json'))
        m.get("{}/api/v1/entity/infrastructure/processes".format(url), status_code=200,
              text=read_file('process_response.json'))
        m.get("{}/api/v1/entity/infrastructure/process-groups".format(url), status_code=200,
              text=read_file('process-group_response.json'))
        m.get("{}/api/v2/entities".format(url), status_code=200,
              text=read_file('custom_device_response.json'))
        m.get('{}/api/v1/events?from={}'.format(url, timestamp), status_code=200,
              text=read_file('9_events_response.json'))
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.OK)
        assert len(topology.get_snapshot('').get('components')) == 15
        assert len(aggregator.events) == 23
        real_events = [e for e in aggregator.events if 'source:StackState Agent' not in e.get('tags', [])]
        simulated_events = [e for e in aggregator.events if 'source:StackState Agent' in e.get('tags', [])]
        assert len(real_events) == 8
        assert len(simulated_events) == 15
        assert len(telemetry._topology_events) == 1


def test_link_to_dynatrace(dynatrace_check, test_instance):
    url = test_instance['url']
    dynatrace_entities_cache["123"] = {"name": "test123", "type": "service"}
    dynatrace_entities_cache["456"] = {"name": "test456", "type": "process-group"}
    dynatrace_entities_cache["789"] = {"name": "test789", "type": "process"}
    dynatrace_entities_cache["abc"] = {"name": "testABC", "type": "host"}
    dynatrace_entities_cache["def"] = {"name": "testDEF", "type": "application"}

    service_url = dynatrace_check._link_to_dynatrace("123", url)
    assert service_url == "https://instance.live.dynatrace.com/#newservices/serviceOverview;id=123"

    process_group_url = dynatrace_check._link_to_dynatrace("456", url)
    assert process_group_url == "https://instance.live.dynatrace.com/#processgroupdetails;id=456"

    process_url = dynatrace_check._link_to_dynatrace("789", url)
    assert process_url == "https://instance.live.dynatrace.com/#processdetails;id=789"

    host_url = dynatrace_check._link_to_dynatrace("abc", url)
    assert host_url == "https://instance.live.dynatrace.com/#newhosts/hostdetails;id=abc"

    application_url = dynatrace_check._link_to_dynatrace("def", url)
    assert application_url == "https://instance.live.dynatrace.com/#uemapplications/uemappmetrics;uemapplicationId=def"


def test_endpoint_generation(dynatrace_client):
    urls = ["https://custom.domain.com/e/abc123", "https://custom.domain.com/e/abc123/"]
    paths = ["api/v1/entity/infrastructure/processes", "/api/v1/entity/infrastructure/processes"]
    expected_url = "https://custom.domain.com/e/abc123/api/v1/entity/infrastructure/processes"
    for url in urls:
        for path in paths:
            assert dynatrace_client.get_endpoint(url, path) == expected_url


def test_unicode_in_response_text(dynatrace_check, test_instance):
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        m.get("{}/api/v1/entity/infrastructure/hosts".format(url), status_code=200,
              text=read_file('host_response.json'))
        m.get("{}/api/v1/entity/applications".format(url), status_code=200, text='[]')
        m.get("{}/api/v1/entity/services".format(url), status_code=200, text='[]')
        m.get("{}/api/v1/entity/infrastructure/processes".format(url), status_code=200, text='[]')
        m.get("{}/api/v1/entity/infrastructure/process-groups".format(url), status_code=200, text='[]')
        m.get("{}/api/v2/entities".format(url), status_code=200, text='{"entities":[]}')
        m.get('{}/api/v1/events?from={}'.format(url, timestamp), status_code=200,
              text=read_file('unicode_topology_event_response.json'))
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.OK)
        unicode_data = topology.get_snapshot('').get('components')[0]['data']['osVersion']
        assert unicode_data == 'Windows Server 2016 Datacenter 1607, ver. 10.0.14393 with unicode char: '
        assert telemetry._topology_events[0]['msg_text'] == 'PROCESS_RESTART on aws-cni™'
