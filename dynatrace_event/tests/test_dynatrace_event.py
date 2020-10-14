# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.dynatrace_event import DynatraceEventCheck, util, EventLimitReachedException
from stackstate_checks.base.stubs import aggregator

import pytest
import unittest
import os
import mock
import yaml
import shutil
import json


def read_data(filename):
    with open("./tests/samples/" + filename, "r") as f:
        data = yaml.safe_load(f)
        return data


def sort_events_data(events):
    events = [json.dumps(event, sort_keys=True) for event in events]
    return events


@pytest.mark.usefixtures("instance")
class TestDynatraceEventCheck(unittest.TestCase):
    """Basic Test for Dynatrace integration."""
    CHECK_NAME = 'dynatrace'
    SERVICE_CHECK_NAME = "dynatrace"

    def setUp(self):
        """
        Initialize and setup the check
        """
        config = {}
        self.check = DynatraceEventCheck(self.CHECK_NAME, config, instances=[self.instance])

        # override the path as the conf.d folder doesn't exist here
        util.DYNATRACE_STATE_FILE = os.getcwd() + "/dynatrace_event.d/dynatrace_event_state.pickle"
        if not os.path.exists(os.getcwd()+"/dynatrace_event.d/"):
            os.mkdir(os.getcwd() + "/dynatrace_event.d/")

        # this is needed because the topology retains data across tests
        aggregator.reset()

    def tearDown(self):
        """
        Destroy the environment
        """
        if os.path.exists(os.getcwd()+"/dynatrace_event.d/"):
            print("deleting the dir")
            shutil.rmtree(os.getcwd()+"/dynatrace_event.d/")

    def test_check_for_empty_events(self):
        """
        Testing Dynatrace event check should not produce any events
        """
        self.check.get_json_response = mock.MagicMock()
        self.check.get_json_response.return_value = []
        self.check.url = self.instance.get('url')

        self.check.check(self.instance)

        events = aggregator.events
        self.assertEqual(len(events), 0)

    def test_check_for_events_process_limit(self):
        """
        Testing Dynatrace should respect `events_process_limit` config and just produce those number of events
        """
        self.check.get_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')
        self.instance["events_process_limit"] = 10

        self.check.check(self.instance)

        events = sort_events_data(aggregator.events)
        self.assertEqual(len(events), self.instance.get("events_process_limit"))
        # make sure we have only 2 open events in state
        dynatrace_state = {
            self.instance.get('url'): 1600875212803,
            self.instance.get('url') + "/events": {
                "SERVICE-FAA29C9BB1C02F9B": {
                    "FAILURE_RATE_INCREASED": {
                        "eventId": -1920904455712359000,
                        "startTime": 1600874700000,
                        "endTime": -1,
                        "entityId": "SERVICE-FAA29C9BB1C02F9B",
                        "entityName": "Ivory Server CTP Inbound PROD",
                        "severityLevel": "ERROR",
                        "impactLevel": "SERVICE",
                        "eventType": "FAILURE_RATE_INCREASED",
                        "eventStatus": "OPEN",
                        "tags": [
                            {
                                "context": "CONTEXTLESS",
                                "key": "app-ivory"
                            },
                            {
                                "context": "CONTEXTLESS",
                                "key": "comp-ivory_to_ctp"
                            },
                            {
                                "context": "CONTEXTLESS",
                                "key": "product-bcops"
                            },
                            {
                                "context": "CONTEXTLESS",
                                "key": "stage",
                                "value": "prod"
                            }
                        ],
                        "id": "-1920904455712358970_1600874700000",
                        "affectedRequestsPerMinute": 35.4,
                        "service": "Ivory Server CTP Inbound PROD",
                        "source": "builtin",
                        "serviceMethod": "/soap/DistributionEinheitInfoGet_5"
                    }
                },
                "SERVICE-9B16B9C5B03836C5": {
                    "FAILURE_RATE_INCREASED": {
                        "eventId": 7799395567706106000,
                        "startTime": 1600874820000,
                        "endTime": -1,
                        "entityId": "SERVICE-9B16B9C5B03836C5",
                        "entityName": "RequestService",
                        "severityLevel": "ERROR",
                        "impactLevel": "SERVICE",
                        "eventType": "FAILURE_RATE_INCREASED",
                        "eventStatus": "OPEN",
                        "tags": [
                            {
                                "context": "CONTEXTLESS",
                                "key": "component",
                                "value": "ant-*"
                            },
                            {
                                "context": "CONTEXTLESS",
                                "key": "k8s-namespace",
                                "value": "schaden-anliegentracking-prod-axa-ch"
                            },
                            {
                                "context": "CONTEXTLESS",
                                "key": "stage",
                                "value": "prod"
                            }
                        ],
                        "id": "7799395567706106116_1600874820000",
                        "affectedRequestsPerMinute": 76.6,
                        "service": "RequestService",
                        "source": "builtin",
                        "serviceMethod": "getRequests"
                    }
                }
            }
        }
        self.assertEqual(self.check.state.data, dynatrace_state)

    def test_check_for_event_limit_reached_condition(self):
        """
        Testing Dynatrace should throw `EventLimitReachedException` if the number of events
        between subsequent check runs exceed the `events_process_limit` and reset the state completely
        """
        self.check.get_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')

        self.check.check(self.instance)

        # first run events will be stored in the state file
        self.assertIsNotNone(self.check.state)
        self.assertIn(self.instance.get('url'), self.check.state.data)

        # agent stopped for few days and started again
        self.check.get_json_response = mock.MagicMock(return_value=read_data("events.json"))
        # since response contains more than 1000 events, this check run should throw EventLimitReachedException
        self.assertRaises(EventLimitReachedException, self.check.check(self.instance))
        # check if the state is reset meaning there should be no data for this instance
        self.assertFalse(self.check.state.data)

    def test_check_for_error_in_events(self):
        """
        Testing Dynatrace check should produce events
        """
        self.check.get_json_response = mock.MagicMock(return_value={"error": {"message": "error occured"}})
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')

        # should throw an exception because of error in response
        self.assertRaises(Exception, self.check.check(self.instance), "Error in pulling the events : error occured")

    def test_check_for_full_events(self):
        """
        Testing Dynatrace check should produce full events
        """
        self.check.get_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')
        self.instance["events_process_limit"] = 1000

        self.check.check(self.instance)

        events = aggregator.events
        events = sort_events_data(events)
        expected_out_events = sort_events_data(read_data("full_health_output_events.json"))
        self.assertEqual(len(events), len(expected_out_events))
        for event in events:
            self.assertIn(event, expected_out_events)

    def test_check_run_with_next_cursor(self):
        """
        Testing Dynatrace event check should be looping through nextCursor until
        it is null or reach `events_process_limit`
        """
        self.check.get_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')
        self.instance["events_process_limit"] = 100

        self.check.check(self.instance)

        events = aggregator.events
        events = sort_events_data(events)
        expected_out_events = sort_events_data(read_data("full_health_output_events.json"))
        self.assertEqual(len(events), len(expected_out_events))
        for event in events:
            self.assertIn(event, expected_out_events)

    def test_check_run_start_from_last_event_timestamp(self):
        """
        Testing Dynatrace event check should be looping through nextCursor until
        it is null or reach `events_process_limit`
        """
        self.check.get_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')
        self.instance["events_process_limit"] = 1000

        self.check.check(self.instance)
        # check if the state file has last event timestamp stored
        self.assertIsNotNone(self.check.state.data[self.instance.get('url')], 1600875212803)

        # check runs 2nd time and calls event API with last stored timestamp which will be in response
        from_timestamp = read_data("next_run_events.json").get("from")
        self.assertEqual(from_timestamp, self.check.state.data[self.instance.get('url')])

    def test_check_raise_exception(self):
        """
        Test to raise a check exception when API endpoint throws exception
        """

        self.check.get_json_response = mock.MagicMock(side_effect=Exception("Exception occured"))
        # self.check.get_json_response.side_effect = Exception("Exception occured")

        self.assertRaises(Exception, self.check.check(self.instance), "Exception occured")
        # no events should occur
        self.assertEqual(len(aggregator.events), 0)
