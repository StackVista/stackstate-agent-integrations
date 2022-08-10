# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest

from .mock import MockedSplunkEvent

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit

CHECK_NAME = "splunk_event"


def test_splunk_error_response(mocked_splunk_event, instance, saved_searches_error, aggregator):
    """Splunk event check should handle a FATAL message response."""
    assert mocked_splunk_event.run() == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(MockedSplunkEvent.SERVICE_CHECK_NAME,
                                    status=MockedSplunkEvent.CRITICAL,
                                    count=1)


def test_splunk_empty_events(mocked_splunk_event, instance, saved_searches_empty, aggregator):
    """Splunk event check should process empty response correctly."""
    assert mocked_splunk_event.run() == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(MockedSplunkEvent.SERVICE_CHECK_NAME,
                                    status=MockedSplunkEvent.OK,
                                    count=2)


def test_splunk_minimal_events(mocked_splunk_event, instance, saved_searches_minimal_events, aggregator):
    """Splunk event check should process minimal response correctly."""
    assert mocked_splunk_event.run() == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(MockedSplunkEvent.SERVICE_CHECK_NAME,
                                    status=MockedSplunkEvent.CRITICAL,
                                    count=1)
    assert len(aggregator.events) == 2, "There should be two events processed."


def test_splunk_full_events(mocked_splunk_event, instance, saved_searches_full_events, aggregator):
    """Splunk event check should process full response correctly."""
    assert mocked_splunk_event.run() == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(MockedSplunkEvent.SERVICE_CHECK_NAME,
                                    status=MockedSplunkEvent.OK,
                                    count=2)

    assert len(aggregator.events) == 2, "There should be two events processed."

    first_event_data = {
        'event_type': "some_type",
        'timestamp': 1488997796.0,
        'msg_title': "some_title",
        'source_type_name': 'some_type', }
    first_event_tags = [
        "VMName:SWNC7R049",
        "alarm_name:Virtual machine CPU usage",
        'from:grey',
        "full_formatted_message:Alarm 'Virtual machine CPU usage' on SWNC7R049 changed from Gray to Green",
        "host:172.17.0.1",
        "key:19964908",
        "to:green",
        "checktag:checktagvalue"]
    aggregator.assert_event(msg_text="some_text", count=1, tags=first_event_tags, **first_event_data)

    second_event_data = {
        'event_type': "some_type",
        'timestamp': 1488997797.0,
        'msg_title': "some_title",
        'source_type_name': 'some_type',
    }
    second_event_tags = [
        "VMName:SWNC7R049",
        "alarm_name:Virtual machine memory usage",
        'from:grey',
        "full_formatted_message:Alarm 'Virtual machine memory usage' on SWNC7R049 changed from Gray to Green",
        "host:172.17.0.1",
        "key:19964909",
        "to:green",
        "checktag:checktagvalue",
    ]
    aggregator.assert_event(msg_text="some_text", count=1, tags=second_event_tags, **second_event_data)
