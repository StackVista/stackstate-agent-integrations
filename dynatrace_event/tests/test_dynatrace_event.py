# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import json
import os
import unittest

import mock
import pytest
import requests_mock
import yaml

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.stubs import aggregator
from stackstate_checks.dynatrace_event.dynatrace_event import generate_bootstrap_timestamp


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
        m.get(url, status_code=200, text=read_data_from_file('full_events.json'))
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
        m.get(url1, status_code=200, text=read_data_from_file("events01.json"))
        m.get(url2, status_code=200, text=read_data_from_file("events02.json"))
        m.get(url3, status_code=200, text=read_data_from_file("events03.json"))
        check.run()
        events = sort_events_data(aggregator.events)
        service_checks = aggregator.service_checks('dynatrace_event')
        assert len(events) == 12
        assert len(service_checks) == 1
        assert service_checks[0].status == AgentCheck.OK


def test_check_for_error_in_events(check):
    """
    Testing Dynatrace check should produce service check when error thrown
    """
    error_msg = "mocked test error occurred"
    check.get_dynatrace_event_json_response = mock.MagicMock(return_value={"error": {"message": error_msg}})
    check.run()
    assert len(aggregator.events) == 0
    service_checks = aggregator.service_checks('dynatrace_event')
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
        assert len(aggregator.events) == 0
        service_checks = aggregator.service_checks('dynatrace_event')
        assert len(service_checks) == 1
        assert service_checks[0].status == AgentCheck.CRITICAL
        assert service_checks[0].message == 'Got 500 when hitting https://instance.live.dynatrace.com/api/v1/events'


def test_check_raise_exception(check):
    """
    Test to raise a check exception when code that talks to API endpoint throws exception
    """
    check.get_dynatrace_event_json_response = mock.MagicMock(side_effect=Exception("Mocked exception occurred"))
    check.run()
    assert len(aggregator.events) == 0
    service_checks = aggregator.service_checks("dynatrace_event")
    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL
    assert service_checks[0].message == 'Mocked exception occurred'


@pytest.mark.usefixtures("instance")
class TestDynatraceEventCheck(unittest.TestCase):
    """Basic Test for Dynatrace integration."""
    CHECK_NAME = 'dynatrace_event'
    SERVICE_CHECK_NAME = "dynatrace_event"

    # def setUp(self):
    #     """
    #     Initialize and setup the check
    #     """
    #     config = {}
    #     self.check = DynatraceEventCheck(self.CHECK_NAME, config, instances=[instance])
    #
    #     # self.events_d_path = os.getcwd() + "/dynatrace_event.d/"
    #     #
    #     # # patch the `DYNATRACE_STATE_FILE` path in util as the conf.d folder doesn't exist here
    #     # util.DYNATRACE_STATE_FILE = self.events_d_path + "dynatrace_event_state.pickle"
    #     #
    #     # if not os.path.exists(self.events_d_path):
    #     #     os.mkdir(os.getcwd() + "/dynatrace_event.d/")
    #     #
    #
    #     # this is needed because the aggregator retains data across tests
    #     aggregator.reset()

    # def tearDown(self):
    #     """
    #     Destroy the environment
    #     """
    #     if os.path.exists(self.events_d_path):
    #         shutil.rmtree(self.events_d_path)

    def test_check_for_full_events(self):
        """
        Testing Dynatrace check should produce full events
        """
        self.check.get_dynatrace_event_json_response = mock.MagicMock(return_value=read_collection_from_file(
            "full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')
        self.instance["events_process_limit"] = 1000

        self.check.check(self.instance)

        events = aggregator.events
        events = sort_events_data(events)
        print(events)
        expected_out_events = sort_events_data(read_collection_from_file("full_health_output_events.json"))
        self.assertEqual(len(events), len(expected_out_events))
        for event in events:
            self.assertIn(event, expected_out_events)


class MockResponse:
    """
    Mocked Response for a session
    """

    def __init__(self, response):
        self.status_code = response.get("status_code")
        self.text = response.get("text")


def read_collection_from_file(filename):
    path_to_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', filename)
    with open(path_to_file, "r") as f:
        return yaml.safe_load(f)


def read_data_from_file(filename):
    path_to_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', filename)
    with open(path_to_file, "r") as f:
        return f.read()


def sort_events_data(events):
    events = [json.dumps(event, sort_keys=True) for event in events]
    return events
