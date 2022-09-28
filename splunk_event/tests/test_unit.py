# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import freezegun
import pytest

from stackstate_checks.base.utils.common import load_json_from_file
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config.splunk_instance_config import time_to_seconds
from stackstate_checks.splunk.saved_search_helper import SavedSearchesTelemetry
from stackstate_checks.splunk_event import SplunkEvent
from .conftest import extract_title_and_type_from_event, common_requests_mocks, list_saved_searches_mock, \
    basic_auth_mock, job_results_mock, search_job_finalized_mock, batch_job_results_mock, saved_searches_error_mock, \
    dispatch_search_error_mock, dispatch_search_mock, SID, OTHER_SID

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit

# test_data is used in _mock_dispatch
test_data = {
    "earliest_time": "",
    "latest_time": ""
}


def _reset_test_data():
    test_data["earliest_time"] = ""
    test_data["latest_time"] = ""


def _setup_client_with_mocked_dispatch(monkeypatch, requests_mock, results_file, mocked_dispatch=None):
    def _mocked_dispatch_assert_earliest_latest_time(*args, **kwargs):
        earliest_time = args[4]['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"], "earliest_time should match"
        if test_data["latest_time"] == "":
            assert 'dispatch.latest_time' not in args[4], "there should not be latest_time in params"
        elif test_data["latest_time"] != "":
            assert args[4]['dispatch.latest_time'] == test_data["latest_time"], "latest_time should match"
        return SID

    if not mocked_dispatch:
        mocked_dispatch = _mocked_dispatch_assert_earliest_latest_time
    basic_auth_mock(requests_mock)
    list_saved_searches_mock(requests_mock)
    job_results_mock(requests_mock, results_file)
    monkeypatch.setattr(SplunkClient, "dispatch", mocked_dispatch)
    _reset_test_data()


def test_splunk_default_integration_events(splunk_event_check, aggregator, requests_mock):
    """
    Run Splunk event check for saved search `test_events` that is used for integration tests.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="test_events_response.json")
    check_result = splunk_event_check.run()
    assert check_result == "", "No errors when running Splunk check."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 4, "There should be four events processed."
    for event in load_json_from_file("test_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def test_splunk_error_response(splunk_event_check, requests_mock, caplog, aggregator):
    """
    Splunk event check should handle a FATAL message response.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="error_response.json")
    run_result = splunk_event_check.run()
    assert "Splunk metric failed with message: No saved search was successfully" \
           in run_result, "Check run result should return error message."
    assert "FATAL exception from Splunk" in caplog.text, "Splunk sends FATAL message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.CRITICAL, count=1)
    assert len(aggregator.events) == 0, "There should be no events processed."


def test_splunk_empty_events(splunk_event_check, requests_mock, aggregator):
    """
    Splunk event check should process empty response correctly.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="empty_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 0, "There should be no events."


def test_splunk_minimal_events(splunk_event_check, requests_mock, aggregator):
    """
    Splunk event check should process minimal response correctly.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="minimal_events_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 2, "There should be two events processed."
    for event in load_json_from_file("minimal_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=2, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def test_splunk_partially_incomplete_events(splunk_event_check, requests_mock, aggregator):
    """
    Splunk event check should continue processing even when some events are not complete.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="partially_incomplete_events_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 1, "There should be one event processed."
    for event in load_json_from_file("partially_incomplete_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def test_splunk_full_events(splunk_event_check, requests_mock, aggregator):
    """
    Splunk event check should process full response correctly.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="full_events_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)

    assert len(aggregator.events) == 2, "There should be two events processed."
    for event in load_json_from_file("full_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def test_splunk_earliest_time_and_duplicates(splunk_event_check, requests_mock, batch_size_2, aggregator):
    """
    Splunk event check should poll batches responses.
    """
    with freezegun.freeze_time("2017-03-08 18:29:59"):
        # Initial run
        common_requests_mocks(requests_mock)
        initial_run_response_files = [
            "batch_poll1_1_response.json", "batch_poll1_2_response.json", "batch_last_response.json"
        ]
        batch_job_results_mock(requests_mock, initial_run_response_files, 2)
        run_result_01 = splunk_event_check.run()
        assert run_result_01 == "", "No errors when running Splunk check."
        aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
        assert len(aggregator.events) == 4, "There should be four events processed."
        assert [e['event_type'] for e in aggregator.events] == ['0_1', '0_2', '1_1', '1_2']

        assert splunk_event_check.get_state() == {'test_events': time_to_seconds("2017-03-08T18:29:59")}

    # Respect earliest_time
    with freezegun.freeze_time("2017-03-08 18:30:00"):
        next_run_response_files = ["batch_poll2_1_response.json", "batch_last_response.json"]
        batch_job_results_mock(requests_mock, next_run_response_files, 2)
        search_job_finalized_mock(requests_mock)
        run_result_02 = splunk_event_check.run()
        assert run_result_02 == "", "No errors when running Splunk check."
        assert len(aggregator.events) == 5, "There should be five event processed."
        assert [e['event_type'] for e in aggregator.events] == ['0_1', '0_2', '1_1', '1_2', '2_1']

        assert splunk_event_check.get_state() == {'test_events': time_to_seconds("2017-03-08T18:30:00")}

        # Throw exception during search
        batch_job_results_mock(requests_mock, ["error_response.json"], 2)
        run_result_03 = splunk_event_check.run()
        assert "Splunk metric failed with message: No saved search was successfully" \
               in run_result_03, "Check run result should return error message."
        aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.CRITICAL, count=1)
        assert len(aggregator.events) == 5, "There still should be five event processed."
        assert [e['event_type'] for e in aggregator.events] == ['0_1', '0_2', '1_1', '1_2', '2_1']


def test_splunk_delay_first_time(splunk_event_check, requests_mock, initial_delay_60_seconds, aggregator):
    """
    Splunk event check should only start polling after the specified time.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="minimal_events_response.json")
    with freezegun.freeze_time("2022-08-23 12:00:01"):
        assert splunk_event_check.run() == ''
        assert len(aggregator.events) == 0

    with freezegun.freeze_time("2022-08-23 12:00:30"):
        assert splunk_event_check.run() == ''
        assert len(aggregator.events) == 0

    with freezegun.freeze_time("2022-08-23 12:01:02"):
        assert splunk_event_check.run() == ''
        assert len(aggregator.events) == 2


def test_splunk_deduplicate_events_in_the_same_run(splunk_event_check, requests_mock, batch_size_2, aggregator):
    """
    Splunk event check should deduplicate events.
    """
    common_requests_mocks(requests_mock)
    response_files = ["batch_no_dup_response.json", "batch_last_response.json"]
    batch_job_results_mock(requests_mock, response_files, 2)
    check_result = splunk_event_check.run()
    assert check_result == "", "No errors when running Splunk check."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    assert len(aggregator.events) == 2, "There should be two events processed."
    assert [e["event_type"] for e in aggregator.events] == ["1", "2"]


def test_splunk_continue_after_restart(splunk_event_check, restart_history_86400, requests_mock, aggregator,
                                       monkeypatch):
    """
    Splunk event check should continue where it left off after restart.
    """
    with freezegun.freeze_time("2017-03-08 00:00:00"):
        _setup_client_with_mocked_dispatch(monkeypatch, requests_mock, "empty_response.json")

        # Initial run with initial time
        test_data["earliest_time"] = "2017-03-08T00:00:00.000000+0000"
        check_result = splunk_event_check.run()
        assert check_result == "", "No errors when running Splunk check."
        assert len(aggregator.events) == 0
        assert splunk_event_check.get_state() == {'test_events': time_to_seconds("2017-03-08T00:00:00")}

    # Restart check and recover data
    with freezegun.freeze_time("2017-03-08 01:00:05.000000"):
        for slice_num in range(0, 12):
            test_data["earliest_time"] = "2017-03-08T00:%s:01.000000+0000" % str(slice_num * 5).zfill(2)
            test_data["latest_time"] = "2017-03-08T00:%s:01.000000+0000" % str((slice_num + 1) * 5).zfill(2)
            if slice_num == 11:
                test_data["latest_time"] = "2017-03-08T01:00:01.000000+0000"
            check_result = splunk_event_check.run()
            assert check_result == "", "No errors when running Splunk check."

        # Now continue with real-time polling (the earliest time taken from last event or last restart chunk)
        test_data["earliest_time"] = "2017-03-08T01:00:01.000000+0000"
        test_data["latest_time"] = ""
        check_result = splunk_event_check.run()
        assert check_result == "", "No errors when running Splunk check."
        assert splunk_event_check.get_state() == {'test_events': time_to_seconds("2017-03-08T01:00:01")}


@freezegun.freeze_time("2017-03-09 00:00:00")
def test_splunk_query_initial_history(requests_mock, initial_history_86400, splunk_event_check, monkeypatch,
                                      aggregator):
    """
    Splunk event check should continue where it left off after restart.
    """
    _setup_client_with_mocked_dispatch(monkeypatch, requests_mock, "empty_response.json")

    # Gather initial data
    for slice_num in range(0, 23):
        test_data["earliest_time"] = '2017-03-08T%s:00:00.000000+0000' % (str(slice_num).zfill(2))
        test_data["latest_time"] = '2017-03-08T%s:00:00.000000+0000' % (str(slice_num + 1).zfill(2))
        check_result = splunk_event_check.run()
        assert check_result == "", "No errors when running Splunk check."

    # Now continue with real-time polling (the earliest time taken from last event)
    test_data["earliest_time"] = "2017-03-08T23:00:00.000000+0000"
    test_data["latest_time"] = ""
    job_results_mock(requests_mock, "minimal_events_response.json")
    check_result = splunk_event_check.run()
    assert check_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2


def test_splunk_max_restart_time(max_restart_time, requests_mock, monkeypatch, aggregator, unit_test_instance,
                                 unit_test_config):
    """
    Splunk event check should use the max restart time parameter.
    """

    def _mocked_dispatch_assert_earliest_time(*args, **kwargs):
        earliest_time = args[4]['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"], "earliest_time should match"
        return SID

    _setup_client_with_mocked_dispatch(monkeypatch, requests_mock, "empty_response.json",
                                       mocked_dispatch=_mocked_dispatch_assert_earliest_time)

    with freezegun.freeze_time("2017-03-08 00:00:00"):
        # Initial run with initial time
        test_data["earliest_time"] = '2017-03-08T00:00:00.000000+0000'
        check = SplunkEvent("splunk", unit_test_config, {}, [unit_test_instance])
        check.check_id = "first_splunk_check_id"
        check_result = check.run()
        assert check_result == "", "No errors when running Splunk check."
        assert len(aggregator.events) == 0

    # Restart check and recover data, taking into account the max restart history
    with freezegun.freeze_time("2017-03-08 12:00:00"):
        test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'
        test_data["latest_time"] = '2017-03-08T11:00:00.000000+0000'
        check = SplunkEvent("splunk", unit_test_config, {}, [unit_test_instance])
        check.check_id = "second_splunk_test_id"
        check_result = check.run()
        assert check_result == "", "No errors when running Splunk check."


@freezegun.freeze_time("2017-03-08 11:00:00")
def test_splunk_keep_time_on_failure(requests_mock, monkeypatch, splunk_event_check, aggregator):
    """
    Splunk event check should keep the same start time when commit fails.
    """
    _setup_client_with_mocked_dispatch(monkeypatch, requests_mock, "minimal_events_response.json")

    test_data["earliest_time"] = "2017-03-08T11:00:00.000000+0000"
    check_result = splunk_event_check.run()
    assert check_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2

    test_data["earliest_time"] = '2017-03-08T12:00:01.000000+0000'
    check_result = splunk_event_check.run()
    assert check_result == "", "No errors when running Splunk check."


@freezegun.freeze_time("2017-03-08 11:00:00")
def test_splunk_advance_time_on_success(monkeypatch, requests_mock, splunk_event_check, aggregator):
    """
    Splunk event check should advance the start time when commit succeeds.
    """
    _setup_client_with_mocked_dispatch(monkeypatch, requests_mock, "minimal_events_response.json")

    test_data["earliest_time"] = "2017-03-08T11:00:00.000000+0000"

    check_result = splunk_event_check.run()
    assert check_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2

    # Make sure we advance the start time
    test_data["earliest_time"] = "2017-03-08T12:00:01.000000+0000"
    assert check_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2


@freezegun.freeze_time("2017-03-08 12:00:00")
def test_splunk_wildcard_searches(requests_mock, wildcard_saved_search, splunk_event_check, aggregator):
    """
    Splunk event check should process minimal response correctly
    """
    basic_auth_mock(requests_mock)
    list_saved_searches_mock(requests_mock, search_results=["test_events_01", "test_events_02", "blaat"])
    dispatch_search_mock(requests_mock, "test_events_01")
    dispatch_search_mock(requests_mock, "test_events_02", sid=OTHER_SID)
    job_results_mock(requests_mock, response_file="minimal_events_response.json")
    job_results_mock(requests_mock, response_file="minimal_events_response.json", sid=OTHER_SID)
    run_result = splunk_event_check.run()
    assert run_result == "", "Check run result shouldn't return error message."
    assert len(aggregator.events) == 4
    assert splunk_event_check.get_state() == {'test_events_01': time_to_seconds("2017-03-08 12:00:00"),
                                              'test_events_02': time_to_seconds("2017-03-08 12:00:00")}


def test_splunk_saved_searches_error(requests_mock, splunk_event_check, aggregator):
    """
    Splunk event check should have a service check failure when getting an exception from saved searches.
    """
    basic_auth_mock(requests_mock)
    saved_searches_error_mock(requests_mock)
    run_result = splunk_event_check.run()
    assert run_result != ""
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.CRITICAL, count=1)


def test_splunk_saved_searches_ignore_error(requests_mock, splunk_event_check, aggregator, ignore_saved_search_errors):
    """
    Splunk event check should ignore exception when getting an exception from saved searches.
    """
    basic_auth_mock(requests_mock)
    saved_searches_error_mock(requests_mock)
    run_result = splunk_event_check.run()
    job_results_mock(requests_mock, response_file="empty_response.json")
    assert run_result == ""
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.CRITICAL, count=1)


def test_splunk_event_respect_parallel_dispatches(requests_mock, monkeypatch, multiple_saved_searches,
                                                  splunk_event_check):
    expected_sid_increment = 1

    def _mock_dispatch_and_await_search(self, process_data, service_check, log, persisted_state, saved_searches):
        saved_searches_parallel = 2
        n = len(saved_searches)
        assert n <= saved_searches_parallel, "Did not respect configured saved_searches_parallel setting, got: %i" % n
        for saved_search in saved_searches:
            result = saved_search.name
            assert result == "savedsearch%i" % self.expected_sid_increment
            self.expected_sid_increment += 1
        return True

    basic_auth_mock(requests_mock)
    list_saved_searches_mock(requests_mock)
    monkeypatch.setattr(SavedSearchesTelemetry, "_dispatch_and_await_search", _mock_dispatch_and_await_search)
    monkeypatch.setattr(SavedSearchesTelemetry, "expected_sid_increment", expected_sid_increment, raising=False)

    run_result = splunk_event_check.run()
    assert run_result == ""


def test_splunk_selective_fields_for_identification(requests_mock, splunk_event_check, aggregator, selective_events):
    """
    Splunk event check should process events where the unique identifier is set to a selective number of fields.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="identification_fields_selective_events_response.json")
    check_result = splunk_event_check.run()
    assert check_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2, "There should be four events processed."
    for event in load_json_from_file("identification_fields_selective_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                **extract_title_and_type_from_event(event))


def test_splunk_all_fields_for_identification(requests_mock, splunk_event_check, aggregator):
    """
    Splunk event check should process events where the unique identifier is set to all fields in a record.
    """
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="identification_fields_all_events_response.json")
    run1_result = splunk_event_check.run()
    assert run1_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2, "There should be two events processed."
    for event in load_json_from_file("identification_fields_all_events_expected.json", "ci/fixtures"):
        aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                **extract_title_and_type_from_event(event))
    # shouldn't resend events
    run2_result = splunk_event_check.run()
    assert run2_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2, "There should be two events processed."


def test_splunk_event_individual_dispatch_failures(requests_mock, splunk_event_check, aggregator,
                                                   wildcard_saved_search):
    """
    Splunk event check shouldn't fail if individual failures occur when dispatching Splunk searches.
    """
    basic_auth_mock(requests_mock)
    list_saved_searches_mock(requests_mock, search_results=["test_events_01", "test_events_02"])
    dispatch_search_mock(requests_mock, "test_events_01")
    dispatch_search_error_mock(requests_mock, "test_events_02")
    job_results_mock(requests_mock, response_file="minimal_events_response.json")
    run_result = splunk_event_check.run()
    assert run_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2, "There should be two events processed."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.CRITICAL, count=0)
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.WARNING, count=1)


def test_splunk_event_individual_search_failures(requests_mock, splunk_event_check, aggregator, wildcard_saved_search):
    """
    Splunk events check shouldn't fail if individual failures occur when executing Splunk searches.
    """
    basic_auth_mock(requests_mock)
    list_saved_searches_mock(requests_mock, search_results=["test_events_01", "test_events_02"])
    dispatch_search_mock(requests_mock, "test_events_01")
    dispatch_search_mock(requests_mock, "test_events_02", sid=OTHER_SID)
    job_results_mock(requests_mock, response_file="minimal_events_response.json")
    job_results_mock(requests_mock, response_file="minimal_events_error_response.json", sid=OTHER_SID)
    run_result = splunk_event_check.run()
    assert run_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 3, "There should be two events processed."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=2)
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.CRITICAL, count=0)
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.WARNING, count=1)


def test_splunk_event_search_full_failure(requests_mock, splunk_event_check, aggregator, wildcard_saved_search):
    """
    Splunk metric check should fail when all saved searches fail.
    """
    basic_auth_mock(requests_mock)
    list_saved_searches_mock(requests_mock, search_results=["test_events_01", "test_events_02"])
    dispatch_search_error_mock(requests_mock, "test_events_01")
    dispatch_search_error_mock(requests_mock, "test_events_02")
    run_result = splunk_event_check.run()
    assert "Splunk metric failed with message: No saved search was successfully" \
           in run_result, "Check run result should return error message."
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.OK, count=0)
    aggregator.assert_service_check(SplunkEvent.SERVICE_CHECK_NAME, status=SplunkEvent.CRITICAL, count=1)


def test_default_params(requests_mock, splunk_event_check, aggregator):
    """
    When no default parameters are provided, the code should provide the parameters.
    """
    expected_default_parameters = {'dispatch.now': True, 'force_dispatch': True}
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="full_events_response.json")
    check_result = splunk_event_check.run()
    default_params = splunk_event_check.splunk_telemetry_instance.instance_config.default_parameters
    assert check_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2
    assert default_params == expected_default_parameters


def test_non_default_params(requests_mock, splunk_event_check, aggregator, non_default_params):
    """
    When non default parameters are provided, the code should respect them.
    """
    expected_default_parameters = {'respect': 'me'}
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="full_events_response.json")
    check_result = splunk_event_check.run()
    default_params = splunk_event_check.splunk_telemetry_instance.instance_config.default_parameters
    assert check_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2
    assert default_params == expected_default_parameters


def test_overwrite_default_params(requests_mock, splunk_event_check, aggregator, overwrite_default_params):
    """
    When default parameters are overwritten, the code should respect them.
    """
    expected_search_parameters = {"respect": "me"}
    common_requests_mocks(requests_mock)
    job_results_mock(requests_mock, response_file="full_events_response.json")
    check_result = splunk_event_check.run()
    search_params = splunk_event_check.splunk_telemetry_instance.saved_searches.searches[0].parameters
    assert check_result == "", "No errors when running Splunk check."
    assert len(aggregator.events) == 2
    assert expected_search_parameters == {k: v for k, v in search_params.items() if k in expected_search_parameters}
