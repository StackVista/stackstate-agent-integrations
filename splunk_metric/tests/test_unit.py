# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json

import pytest
from freezegun import freeze_time

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.state_common import generate_state_key
from stackstate_checks.splunk.config.splunk_instance_config import time_to_seconds
from .conftest import patch_metric_check, max_query_chunk_sec_history_check

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit


def assert_service_check_status(check, aggregator, count, status_index, status, message=None):
    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)
    assert len(service_checks) == count

    if message is not None:
        assert service_checks[status_index].message == message

    assert service_checks[status_index].status == status, "service check should have status %s" % status


def test_minimal_metrics(config_minimal_metrics, check, telemetry):
    check_response = check.run()
    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1488974400.0)


def test_error_response(config_error, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response != '', "The check run cycle should run a error"

    telemetry.assert_total_metrics(0)
    assert_service_check_status(check, aggregator, count=3, status_index=1, status=AgentCheck.CRITICAL)


def test_empty_metrics(config_empty, check, telemetry, ):
    check_response = check.run()
    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(0)
    telemetry.assert_metric("metric_name", count=0)


def test_partially_incomplete_metrics(config_partially_incomplete_metrics, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(1)
    telemetry.assert_metric("metric_name", count=1, value=1.0, tags=[], hostname='', timestamp=1488974400.0)

    assert_service_check_status(check, aggregator, count=4, status_index=0, status=AgentCheck.WARNING,
                                message="The saved search 'partially_incomplete_metrics' contained 1 "
                                        "incomplete records")


def test_full_metrics(config_full_metrics, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=1, value=1.0, tags=[
        'hostname:myhost',
        'some:tag',
        'checktag:checktagvalue'], hostname='', timestamp=1488997796.0)
    telemetry.assert_metric("metric_name", count=1, value=1.0, tags=[
        'hostname:123',
        'some:123',
        'device_name:123',
        'checktag:checktagvalue'], hostname='', timestamp=1488997797.0)


def test_alternative_fields_metrics(config_alternative_fields_metrics, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1488974400.0)


def test_fixed_metric_name(config_fixed_metric_name, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("custommetric", count=2, value=3.0, tags=["mymetric:metric_name"], hostname='',
                            timestamp=1488974400.0)


def test_warning_on_missing_fields(config_warning_on_missing_fields, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response != '', "The check run cycle SHOULD produce a error"

    assert_service_check_status(check, aggregator, count=3, status_index=0, status=AgentCheck.WARNING)


def test_same_data_metrics(config_same_data_metrics, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=2.0, tags=[], hostname='',
                            timestamp=1488974400.0)


def test_delayed_start(config_delayed_start, check, telemetry, aggregator):
    with freeze_time("1970-01-01T00:00:01Z"):
        check_response = check.run()
        assert check_response == '', "The check run cycle NOT SHOULD produce a error"

        telemetry.assert_total_metrics(0)

    with freeze_time("1970-01-01T00:00:30Z"):
        check_response = check.run()
        assert check_response == '', "The check run cycle NOT SHOULD produce a error"

        telemetry.assert_total_metrics(0)

    with freeze_time("1970-01-01T00:01:02Z"):
        check_response = check.run()
        assert check_response == '', "The check run cycle NOT SHOULD produce a error"

        telemetry.assert_total_metrics(2)
        telemetry.assert_metric("metric_name", count=2, value=3.0, timestamp=1488974400.0)


def test_max_restart_time(config_max_restart_time, patch_max_restart_time, check, telemetry, aggregator):
    with freeze_time("2017-03-08T00:00:00.000000+0000"):
        patch_max_restart_time["earliest_time"] = '2017-03-08T00:00:00.000000+0000'

        check_response = check.run()
        assert check_response == '', "The check run cycle SHOULD NOT produce a error"

        telemetry.assert_total_metrics(0)

    telemetry.reset()
    aggregator.reset()

    with freeze_time("2017-03-08T12:00:00.000000+0000"):
        patch_max_restart_time["earliest_time"] = '2017-03-08T11:00:00.000000+0000'
        patch_max_restart_time["latest_time"] = '2017-03-08T11:00:00.000000+0000'

        check_response = check.run()
        assert check_response == '', "The check run cycle SHOULD NOT produce a error"

        telemetry.assert_total_metrics(0)


def test_metric_check(config_metric_check, check, monkeypatch, transaction, state):
    check_response = check.run()
    assert check_response == '', "The check run should not return a error"

    persistent_state_key = generate_state_key(check._get_instance_key().to_string(), check.PERSISTENT_CACHE_KEY)
    first_transaction = transaction._transactions.get(check.check_id)
    first_state = state.get_state(check, check.check_id, persistent_state_key)

    transaction.assert_started_transaction(check.check_id, False)
    transaction.assert_stopped_transaction(check.check_id, True)
    transaction.assert_discarded_transaction(check.check_id, False)

    check_response = check.run()
    assert check_response == '', "The check run should not return a error"

    persistent_state_key = generate_state_key(check._get_instance_key().to_string(), check.PERSISTENT_CACHE_KEY)
    second_transaction = transaction._transactions.get(check.check_id)
    second_state = state.get_state(check, check.check_id, persistent_state_key)

    transaction.assert_started_transaction(check.check_id, False)
    transaction.assert_stopped_transaction(check.check_id, True)
    transaction.assert_discarded_transaction(check.check_id, False)

    assert first_transaction == second_transaction
    assert first_state == second_state

    patch_metric_check(monkeypatch, True)

    check_response = check.run()
    assert check_response != '', "The check run should return a error"

    persistent_state_key = generate_state_key(check._get_instance_key().to_string(), check.PERSISTENT_CACHE_KEY)
    third_transaction = transaction._transactions.get(check.check_id)
    third_state = state.get_state(check, check.check_id, persistent_state_key)

    transaction.assert_started_transaction(check.check_id, True)
    transaction.assert_stopped_transaction(check.check_id, False)
    transaction.assert_discarded_transaction(check.check_id, True)

    assert third_transaction is not None and third_transaction is not {}
    assert third_state is not None and third_state is not {}


def test_default_parameters(config_test_default_parameters, patch_default_parameters_check, check, telemetry,
                            aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)


@freeze_time("2017-03-08T18:29:59.000000+0000")
def test_earliest_time_and_duplicates(config_earliest_time_and_duplicates, patch_earliest_time_and_duplicates, check,
                                      telemetry, aggregator):
    test_data = patch_earliest_time_and_duplicates

    test_data["sid"] = "poll"

    check_response = check.run()
    assert check_response == '', "The check run cycle NOT SHOULD produce a error"

    telemetry.assert_total_metrics(4)

    telemetry.assert_metric("name", count=4, value=66.0, tags=[], hostname='')
    telemetry.assert_metric("name", count=1, value=11.0, tags=[], hostname='', timestamp=1488997796.0)
    telemetry.assert_metric("name", count=1, value=12.0, tags=[], hostname='', timestamp=1488997797.0)
    telemetry.assert_metric("name", count=1, value=21.0, tags=[], hostname='', timestamp=1488997798.0)
    telemetry.assert_metric("name", count=1, value=22.0, tags=[], hostname='', timestamp=1488997799.0)

    telemetry.reset()
    aggregator.reset()

    test_data["sid"] = "poll1"
    test_data["earliest_time"] = '2017-03-08T18:30:00.000000+0000'

    check_response = check.run()
    assert check_response == '', "The check run cycle NOT SHOULD produce a error"

    telemetry.assert_total_metrics(1)

    telemetry.assert_metric("name", count=1, value=31.0, tags=[], hostname='')
    telemetry.assert_metric("name", count=1, value=31.0, tags=[], hostname='', timestamp=1488997800.0)

    telemetry.reset()
    aggregator.reset()

    test_data["throw"] = True

    check_response = check.run()
    assert check_response != '', "The check run cycle SHOULD produce a error"

    assert_service_check_status(check, aggregator, count=3, status_index=1, status=AgentCheck.CRITICAL)


def test_continue_after_restart(config_continue_after_restart, patch_continue_after_restart, check, telemetry,
                                aggregator):
    test_data = patch_continue_after_restart

    with freeze_time("2017-03-08T00:00:00.000000+0000"):
        # Initial run with initial time
        test_data["earliest_time"] = '2017-03-08T00:00:00.000000+0000'
        test_data["latest_time"] = None

        check_response = check.run()
        assert check_response == '', "The check run cycle should not produce a error"

        telemetry.assert_total_metrics(0)

    with freeze_time("2017-03-08T01:00:05.000000+0000"):
        for slice_num in range(0, 12):
            # Reset stub data to not persist between runs
            telemetry.reset()
            aggregator.reset()

            # Instead of a pyfixture we are importing this check to allow a force_reload behaviour
            test_data = patch_continue_after_restart

            test_data["earliest_time"] = '2017-03-08T00:%s:01.000000+0000' % (str(slice_num * 5).zfill(2))
            test_data["latest_time"] = '2017-03-08T00:%s:01.000000+0000' % (str((slice_num + 1) * 5).zfill(2))
            if slice_num == 11:
                test_data["latest_time"] = '2017-03-08T01:00:01.000000+0000'

            check_response = check.run()
            assert check_response == '', "The check run cycle SHOULD NOT produce a error"

            assert check.continue_after_commit is True

            telemetry.assert_total_metrics(0)
            assert_service_check_status(check, aggregator, count=3, status_index=0, status=AgentCheck.OK)

        telemetry.reset()
        aggregator.reset()

        # # Now continue with real-time polling (the earliest time taken from last event or last restart chunk)
        test_data["earliest_time"] = '2017-03-08T01:00:01.000000+0000'
        test_data["latest_time"] = None

        check_response = check.run()
        assert check_response == '', "The check run cycle SHOULD NOT produce an error"

        assert check.continue_after_commit is False, \
            "As long as we are not done with history, the check should continue"


def test_selective_fields_for_identification_check(config_selective_fields_for_identification_check, check, telemetry,
                                                   aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, timestamp=1923825600)
    telemetry.assert_metric("metric_name", count=1, tags=['uid1:uid', 'uid2:1'], value=1.0, timestamp=1923825600)
    telemetry.assert_metric("metric_name", count=1, tags=['uid1:uid', 'uid2:2'], value=2.0, timestamp=1923825600)

    # Remove the existing metrics to evaluate what the next run gives
    telemetry.reset()

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(0)

    assert_service_check_status(check, aggregator, count=6, status_index=2, status=AgentCheck.OK)


def test_all_fields_for_identification_check(config_all_fields_for_identification_check, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], timestamp=1923825600)

    # Remove the existing metrics to evaluate what the next run gives
    telemetry.reset()

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(0)

    assert_service_check_status(check, aggregator, count=6, status_index=2, status=AgentCheck.OK)


def test_backward_compatibility(config_backward_compatibility_check, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], timestamp=1923825600)

    # Remove the existing metrics to evaluate what the next run gives
    telemetry.reset()

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(0)

    assert_service_check_status(check, aggregator, count=6, status_index=2, status=AgentCheck.OK)


def test_backward_compatibility_new_conf(config_backward_compatibility_new_conf_check, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], timestamp=1923825600)

    # Remove the existing metrics to evaluate what the next run gives
    telemetry.reset()

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(0)

    assert_service_check_status(check, aggregator, count=6, status_index=2, status=AgentCheck.OK)


@freeze_time("2017-03-09T00:00:00.000000+0000")
def test_query_initial_history(config_query_initial_history, patch_query_initial_history, check, telemetry, aggregator):
    test_data = patch_query_initial_history

    # Gather initial data
    for slice_num in range(0, 23):
        test_data["earliest_time"] = '2017-03-08T%s:00:00.000000+0000' % (str(slice_num).zfill(2))
        test_data["latest_time"] = '2017-03-08T%s:00:00.000000+0000' % (str(slice_num + 1).zfill(2))
        check_response = check.run()

        assert check_response == '', "The check run cycle SHOULD NOT produce an error"
        assert check.continue_after_commit is True, "As long as we are not done with history, the check should continue"

    telemetry.reset()

    # Now continue with real-time polling (earliest time taken from last event)
    test_data["earliest_time"] = '2017-03-08T23:00:00.000000+0000'
    test_data["latest_time"] = None

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce an error"

    telemetry.assert_total_metrics(2)
    assert check.continue_after_commit is False, "As long as we are not done with history, the check should continue"


@freeze_time("2017-03-08T11:00:00.000000+0000")
def test_keep_time_on_failure(config_keep_time_on_failure, patch_keep_time_on_failure, check, telemetry, aggregator):
    test_data = patch_keep_time_on_failure

    test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    telemetry.assert_total_metrics(2)

    test_data["earliest_time"] = '2017-03-08T12:00:01.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"


@freeze_time("2017-03-08T11:00:00.000000+0000")
def test_advance_time_on_success(config_advance_time_on_success, patch_advance_time_on_success, check, telemetry,
                                 aggregator):
    test_data = patch_advance_time_on_success

    test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    telemetry.assert_total_metrics(2)

    test_data["earliest_time"] = '2017-03-08T12:00:01.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"


def test_wildcard_searches(config_wildcard_searches, patch_wildcard_searches, check, telemetry, aggregator):
    data = patch_wildcard_searches

    data['saved_searches'] = ["minimal_metrics", "blaat"]
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    telemetry.assert_total_metrics(2)
    assert len(check.splunk_telemetry_instance.saved_searches.searches) == 1

    telemetry.reset()

    data['saved_searches'] = []
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    telemetry.assert_total_metrics(0)
    assert len(check.splunk_telemetry_instance.saved_searches.searches) == 0


def test_saved_searches_error(config_saved_searches_error, patch_saved_searches_error, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response != '', "The check run cycle SHOULD produce a error"

    assert_service_check_status(check, aggregator, count=2, status_index=0, status=AgentCheck.CRITICAL, message="Boom")


def test_saved_searches_ignore_error(config_saved_searches_ignore_error, patch_saved_searches_ignore_error, check,
                                     telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle NOT SHOULD produce a error"

    assert_service_check_status(check, aggregator, count=2, status_index=0, status=AgentCheck.CRITICAL, message="Boom")


def test_individual_dispatch_failures(config_individual_dispatch_failures, patch_individual_dispatch_failures, check,
                                      telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle NOT SHOULD produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, timestamp=1488974400.0)

    assert_service_check_status(check, aggregator, count=4, status_index=0, status=AgentCheck.WARNING,
                                message="BOOM")


def test_individual_search_failures(config_individual_search_failures, patch_individual_search_failures, check,
                                    telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle NOT SHOULD produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, timestamp=1488974400.0)

    assert_service_check_status(check, aggregator, count=4, status_index=0, status=AgentCheck.WARNING,
                                message="Received FATAL exception from Splunk, got: Invalid offset.")


def test_search_full_failure(config_search_full_failure, patch_search_full_failure, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response != '', "The check run cycle SHOULD produce a error"

    assert_service_check_status(check, aggregator, count=3, status_index=1, status=AgentCheck.CRITICAL,
                                message="No saved search was successfully executed.")


def test_non_default_parameters(config_non_default_parameters_check, patch_non_default_parameters_check, check,
                                telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)


def test_overwrite_default_parameters(config_overwrite_default_parameters_check,
                                      patch_overwrite_default_parameters_check, check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)


@freeze_time("2017-03-08T11:58:00.000000+0000")
def test_max_query_chunk_sec_live(config_max_query_chunk_sec_live_check, patch_max_query_chunk_sec_live_check, check,
                                  telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)

    last_observed_timestamp = telemetry.metrics("metric_name")[0].timestamp
    assert last_observed_timestamp == time_to_seconds('2017-03-08T12:00:00.000000+0000')


def test_token_auth_with_valid_token(set_authentication_mode_to_token, config_token_auth_with_valid_token_check, check,
                                     telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", value=3.0, tags=[], timestamp=1488974400.0)

    assert_service_check_status(check, aggregator, count=3, status_index=0, status=AgentCheck.OK)
    assert_service_check_status(check, aggregator, count=3, status_index=2, status=AgentCheck.OK,
                                message=check.CHECK_NAME + " check was processed successfully")


def test_authentication_invalid_token(set_authentication_mode_to_token, config_authentication_invalid_token_check,
                                      check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check SHOULD NOT return a error result after running."

    assert_service_check_status(check, aggregator, count=2, status_index=0, status=AgentCheck.CRITICAL,
                                message="Current in use authentication token is expired. Please provide a valid "
                                        "token in the YAML and restart the Agent")


def test_authentication_token_no_audience_parameter_check(set_authentication_mode_to_token,
                                                          config_authentication_token_no_audience_parameter_check,
                                                          check, telemetry, aggregator):
    check_response = check.run()
    assert check_response != '', "The check SHOULD return a error result after running."

    assert_service_check_status(check, aggregator, count=1, status_index=0, status=AgentCheck.CRITICAL,
                                message="Instance missing \"authentication.token_auth.audience\" value")


def test_authentication_token_no_name_parameter_check(set_authentication_mode_to_token,
                                                      config_authentication_token_no_name_parameter_check,
                                                      check, telemetry, aggregator):
    check_response = check.run()
    assert check_response != '', "The check SHOULD return a error result after running."

    assert_service_check_status(check, aggregator, count=1, status_index=0, status=AgentCheck.CRITICAL,
                                message="Instance missing \"authentication.token_auth.name\" value")


def test_authentication_prefer_token_over_basic_check(config_authentication_prefer_token_over_basic_check,
                                                      check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check SHOULD NOT return a error result after running."

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", value=3.0, tags=[], timestamp=1488974400.0)

    assert_service_check_status(check, aggregator, count=3, status_index=0, status=AgentCheck.OK)


def test_authentication_token_expired_check(set_authentication_mode_to_token, config_authentication_token_expired_check,
                                            check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check SHOULD NOT return a error result after running."

    assert_service_check_status(check, aggregator, count=2, status_index=0, status=AgentCheck.CRITICAL,
                                message="Current in use authentication token is expired. Please provide a valid"
                                        " token in the YAML and restart the Agent")

    assert_service_check_status(check, aggregator, count=2, status_index=1, status=AgentCheck.OK,
                                message=check.CHECK_NAME + " check was processed successfully")


def test_respect_parallel_dispatches(config_respect_parallel_dispatches, patch_respect_parallel_dispatches,
                                     check, telemetry, aggregator):
    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    assert check.parallel_dispatches_failed is False, "The check should pass parallel dispatches"


def test_max_query_chunk_sec_history(monkeypatch, get_logger, requests_mock, splunk_config, splunk_instance_basic_auth,
                                     splunk_metric, telemetry, state, transaction):
    with freeze_time("2017-03-09T00:00:00.000000+0000"):
        check, test_data = max_query_chunk_sec_history_check(monkeypatch, get_logger, requests_mock, splunk_config,
                                                             splunk_instance_basic_auth, splunk_metric)

        test_data["earliest_time"] = '2017-03-08T00:00:00.000000+0000'

        check_response = check.run()
        assert check_response == '', "The check run cycle SHOULD NOT produce a error."

        telemetry.assert_total_metrics(1)

        # Get the latest transaction value to check the last observed timestamp
        key = generate_state_key(check._get_instance_key().to_string(), check.TRANSACTIONAL_PERSISTENT_CACHE_KEY)
        state_value = state.get_state(check, check.check_id, key)
        transactional_state = json.loads(state_value)

        last_observed_timestamp = transactional_state.get("metrics")

        # make sure the window is of max_query_chunk_seconds and last_observed_time_stamp is dispatch latest time - 1
        assert last_observed_timestamp == time_to_seconds('2017-03-08T00:04:59.000000+0000')

    telemetry.reset()

    with freeze_time("2017-03-08T12:00:00.000000+0000"):
        check, test_data = max_query_chunk_sec_history_check(monkeypatch, get_logger, requests_mock, splunk_config,
                                                             splunk_instance_basic_auth, splunk_metric)

        test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'

        check_response = check.run()
        assert check_response == '', "The check run cycle SHOULD NOT produce a error."

        telemetry.assert_total_metrics(2)

        # Get the latest transaction value to check the last observed timestamp
        key = generate_state_key(check._get_instance_key().to_string(), check.TRANSACTIONAL_PERSISTENT_CACHE_KEY)
        state_value = state.get_state(check, check.check_id, key)
        transactional_state = json.loads(state_value)

        last_observed_timestamp = transactional_state.get("metrics")

        # make sure the window is of max_query_chunk_seconds and last_observed_time_stamp is dispatch latest time - 1
        assert last_observed_timestamp == time_to_seconds('2017-03-08T11:04:59.000000+0000')
