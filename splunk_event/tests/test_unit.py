# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest

from .mock import MockedSplunkEvent

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit

CHECK_NAME = "splunk_event"


def test_splunk_error_response(mocked_check, instance, fatal_error, aggregator):
    """Splunk event check should handle a FATAL message response."""
    run_result = mocked_check.run()
    first_error = "Splunk metric failed with message: Received FATAL exception from Splunk"
    assert first_error in run_result, "Check run result should return error message."
    aggregator.assert_service_check(MockedSplunkEvent.SERVICE_CHECK_NAME,
                                    status=MockedSplunkEvent.CRITICAL,
                                    count=1)


def test_splunk_empty_events(mocked_check, instance, empty_result, aggregator):
    """Splunk event check should process empty response correctly."""
    run_result = mocked_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(MockedSplunkEvent.SERVICE_CHECK_NAME,
                                    status=MockedSplunkEvent.OK,
                                    count=2)


def test_splunk_minimal_events(mocked_check, instance, minimal_events, aggregator):
    """Splunk event check should process minimal response correctly."""
    # TODO: does this test make sense?
    run_result = mocked_check.run()
    assert "This field is required" in run_result, "Check run result should return error message."
    aggregator.assert_service_check(MockedSplunkEvent.SERVICE_CHECK_NAME,
                                    status=MockedSplunkEvent.CRITICAL,
                                    count=1)
    assert len(aggregator.events) == 0, "There should be no events processed."


def test_splunk_partially_incomplete_events(mocked_check, instance, partially_incomplete_events,
                                            aggregator):
    """Splunk event check should continue processing even when some events are not complete."""
    # TODO: does this test make sense?
    run_result = mocked_check.run()
    assert "This field is required" in run_result, "Check run result should return error message."
    aggregator.assert_service_check(MockedSplunkEvent.SERVICE_CHECK_NAME,
                                    status=MockedSplunkEvent.CRITICAL,
                                    count=1)
    assert len(aggregator.events) == 0, "There should be no events processed."


def test_splunk_full_events(mocked_check, instance, full_events, aggregator, state, transaction):
    """Splunk event check should process full response correctly."""
    assert mocked_check.run() == "", "Check run result shouldn't return error message."
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
    print(state._state)
    print(transaction._transactions)

    assert 1 == 2


def test_splunk_earliest_time_and_duplicates():
    pass
