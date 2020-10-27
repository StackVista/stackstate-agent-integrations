# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.dynatrace_event import DynatraceEventCheck, util
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


class MockResponse:
    """
    Mocked Response for a session
    """
    def __init__(self, response):
        self.status_code = response.get("status_code")
        self.text = response.get("text")


@pytest.mark.usefixtures("instance")
class TestDynatraceEventCheck(unittest.TestCase):
    """Basic Test for Dynatrace integration."""
    CHECK_NAME = 'dynatrace_event'
    SERVICE_CHECK_NAME = "dynatrace_event"

    def setUp(self):
        """
        Initialize and setup the check
        """
        config = {}
        self.check = DynatraceEventCheck(self.CHECK_NAME, config, instances=[self.instance])

        self.events_d_path = os.getcwd() + "/dynatrace_event.d/"

        # patch the `DYNATRACE_STATE_FILE` path in util as the conf.d folder doesn't exist here
        util.DYNATRACE_STATE_FILE = self.events_d_path + "dynatrace_event_state.pickle"

        if not os.path.exists(self.events_d_path):
            os.mkdir(os.getcwd() + "/dynatrace_event.d/")

        # this is needed because the aggregator retains data across tests
        aggregator.reset()

    def tearDown(self):
        """
        Destroy the environment
        """
        if os.path.exists(self.events_d_path):
            shutil.rmtree(self.events_d_path)

    def test_check_for_empty_events(self):
        """
        Testing Dynatrace event check should not produce any events
        """
        self.check.get_dynatrace_event_json_response = mock.MagicMock()
        self.check.get_dynatrace_event_json_response.return_value = []
        self.check.url = self.instance.get('url')

        self.check.check(self.instance)

        events = aggregator.events
        self.assertEqual(len(events), 0)

    def test_check_for_event_limit_reached_condition(self):
        """
        Testing Dynatrace should throw `EventLimitReachedException` if the number of events
        between subsequent check runs exceed the `events_process_limit` and reset the state completely
        """
        self.check.get_dynatrace_event_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')

        self.check.check(self.instance)
        # first run events will be stored in the state file
        self.assertIsNotNone(self.check.state)
        print(self.check.state.data)
        # TODO also assert that the state that is on disk is the same as check.state
        self.assertIn(self.instance.get('url'), self.check.state.data)

        # make sure we have only 2 open events in state
        dynatrace_state = {
                self.instance.get('url'): {
                    "lastProcessedEventTimestamp": 1600875212803,
                    "events": {
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
        }
        # the state that is on disk should be the same as check.state
        self.assertEqual(self.check.state.data, dynatrace_state)
        self.assertEqual(len(aggregator.events), 2)

        aggregator.reset()
        # agent stopped for few days and started again
        self.check.get_dynatrace_event_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.instance["events_process_limit"] = 2
        self.check.check(self.instance)

        # check that reset events are sent
        self.assertEqual(len(aggregator.events), 2)
        # check if the state is reset and empty state is persisted.
        self.assertFalse(self.check.state.data)

    def test_check_respects_events_process_limit_on_startup(self):
        """
        Testing Dynatrace should respect `events_process_limit` config and just produce those number of events
        """
        self.check.get_dynatrace_event_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')
        self.instance["events_process_limit"] = 10

        self.check.check(self.instance)

        events = sort_events_data(aggregator.events)
        # since response contains 122 events but have to process only 10 events
        # we should only send 2 open events and not closed one
        self.assertEqual(len(events), 2)
        # make sure we have only 2 open events in state
        dynatrace_state = {
            self.instance.get('url'): {
                "lastProcessedEventTimestamp": 1600875212803,
                "events": {
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
        }
        self.assertEqual(self.check.state.data, dynatrace_state)

    def test_check_for_error_in_events(self):
        """
        Testing Dynatrace check should produce service check when error thrown
        """
        self.check.get_dynatrace_event_json_response = mock.MagicMock()
        self.check.get_dynatrace_event_json_response.return_value = {"error": {"message": "error occured"}}
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')

        self.check.check(self.instance)

        # No events were sent to StackState
        self.assertEqual(len(aggregator.events), 0)

    def test_check_for_full_events(self):
        """
        Testing Dynatrace check should produce full events
        """
        self.check.get_dynatrace_event_json_response = mock.MagicMock(return_value=read_data("full_events.json"))
        self.check._current_time_seconds = mock.MagicMock(return_value=1602685050)
        self.check.url = self.instance.get('url')
        self.instance["events_process_limit"] = 1000

        self.check.check(self.instance)

        events = aggregator.events
        events = sort_events_data(events)
        print(events)
        expected_out_events = sort_events_data(read_data("full_health_output_events.json"))
        self.assertEqual(len(events), len(expected_out_events))
        for event in events:
            self.assertIn(event, expected_out_events)

    def test_check_raise_exception(self):
        """
        Test to raise a check exception when API endpoint throws exception
        """

        self.check.get_dynatrace_event_json_response = mock.MagicMock(side_effect=Exception("Exception occured"))

        self.check.check(self.instance)
        # no events should occur
        self.assertEqual(len(aggregator.events), 0)
        service_checks = aggregator.service_checks("dynatrace_event")
        self.assertEqual(len(service_checks), 1)
        self.assertEqual(service_checks[0].name, self.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)

    def test_check_raise_exception_for_response_code_not_200(self):
        """
        Test to raise a check exception when API endpoint throws exception
        """

        self.check.get_dynatrace_event_json_response = mock.MagicMock(return_value=MockResponse({"status_code": 500,
                                                                                                 "text": "error"}))

        self.check.check(self.instance)
        # no events should occur
        self.assertEqual(len(aggregator.events), 0)
        service_checks = aggregator.service_checks("dynatrace_event")
        self.assertEqual(len(service_checks), 1)
        self.assertEqual(service_checks[0].name, self.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)
