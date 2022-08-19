# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json

import pytest
from requests_mock import Mocker

from stackstate_checks.base.utils.common import load_json_from_file, read_file
from stackstate_checks.splunk_event import SplunkEvent
from .conftest import extract_title_and_type_from_event

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit


def test_splunk_error_response(splunk_event_check, requests_mock, caplog, aggregator):
    """Splunk event check should handle a FATAL message response."""
    _setup_request_mocks(requests_mock, response_file="error_response.json")
    run_result = splunk_event_check.run()
    assert "Splunk metric failed with message: No saved search was successfully" \
           in run_result, "Check run result should return error message."
    assert "FATAL exception from Splunk" in caplog.text, "Splunk sends FATAL message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.CRITICAL, count=1)
    assert len(aggregator.events) == 0, "There should be no events processed."


def test_splunk_empty_events(splunk_event_check, requests_mock, aggregator):
    """Splunk event check should process empty response correctly."""
    _setup_request_mocks(requests_mock, response_file="empty_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 0, "There should be no events."


def test_splunk_minimal_events(splunk_event_check, requests_mock, caplog, aggregator):
    """Splunk event check should process minimal response correctly."""
    _setup_request_mocks(requests_mock, response_file="minimal_events_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 2, "There should be two events processed."
    for event in load_json_from_file("minimal_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=2, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def test_splunk_partially_incomplete_events(splunk_event_check, requests_mock, caplog, aggregator):
    """Splunk event check should continue processing even when some events are not complete."""
    _setup_request_mocks(requests_mock, response_file="partially_incomplete_events_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 1, "There should be one event processed."
    for event in load_json_from_file("partially_incomplete_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def test_splunk_full_events(splunk_event_check, requests_mock, aggregator):
    """Splunk event check should process full response correctly."""
    _setup_request_mocks(requests_mock, response_file="full_events_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)

    assert len(aggregator.events) == 2, "There should be two events processed."
    for event in load_json_from_file("full_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def test_splunk_default_integration_events(splunk_event_check, aggregator, requests_mock):
    """Run Splunk event check for saved search `test_events` that is used for integration tests."""
    _setup_request_mocks(requests_mock, response_file="test_events_response.json")
    check_result = splunk_event_check.run()
    assert check_result == '', "No errors when running Splunk check."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 4, "There should be four events processed."
    for event in load_json_from_file("test_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def _setup_request_mocks(requests_mock, response_file):
    # type: (Mocker, str) -> None
    """
    Splunk client request flow: Basic authentication > List saved searches > Dispatch search > Get search results
    """
    # Basic authentication
    requests_mock.post(
        url="http://localhost:8089/services/auth/login?output_mode=json",
        status_code=200,
        text=json.dumps({"sessionKey": "testSessionKey123", "message": "", "code": ""})
    )
    # List saved searches
    requests_mock.get(
        url="http://localhost:8089/services/saved/searches?output_mode=json&count=-1",
        status_code=200,
        text=json.dumps(
            {"entry": [{"name": "Errors in the last 24 hours"},
                       {"name": "Errors in the last hour"},
                       {"name": "test_events"}],
             "paging": {"total": 3, "perPage": 18446744073709552000, "offset": 0},
             "messages": []}
        )
    )
    # Dispatch search and get job's sid
    requests_mock.post(
        url="http://localhost:8089/servicesNS/admin/search/saved/searches/test_events/dispatch",
        status_code=201,
        text=json.dumps({"sid": "admin__admin__search__RMD567222de41fbb54c3_at_1660747475_3"})
    )
    # Get search results for job
    requests_mock.get(
        url="http://localhost:8089/servicesNS/-/-/search/jobs/"
            "admin__admin__search__RMD567222de41fbb54c3_at_1660747475_3/results?output_mode=json&offset=0&count=1000",
        status_code=200,
        text=read_file(response_file, "ci/fixtures")
    )
