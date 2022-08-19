# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.state_common import generate_state_key
from stackstate_checks.splunk.config.splunk_instance_config import time_to_seconds
from .conftest import splunk_continue_after_restart, splunk_config_max_query_chunk_sec_history


@pytest.mark.unit
def test_splunk_error_response(splunk_error_response_check, telemetry, aggregator):
    check = splunk_error_response_check
    check_response = check.run()

    assert check_response != '', "The check run cycle should run a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    telemetry.assert_total_metrics(0)

    assert len(service_checks) == 1  # TODO: Melcom - Verify this changed from 2 to 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "service check should have status AgentCheck.CRITICAL"


@pytest.mark.unit
def test_splunk_metric_check(splunk_metric_check_first_run, splunk_metric_check_second_run,
                             splunk_metric_check_third_run, transaction, state):

    check = splunk_metric_check_first_run
    check_response = check.run()
    assert check_response == '', "The check run should not return a error"

    persistent_state_key = generate_state_key(check._get_instance_key().to_string(), check.PERSISTENT_CACHE_KEY)
    first_transaction = transaction._transactions.get(check.check_id)
    first_state = state.get_state(check, check.check_id, persistent_state_key)

    transaction.assert_started_transaction(check.check_id, False)
    transaction.assert_stopped_transaction(check.check_id, True)
    transaction.assert_discarded_transaction(check.check_id, False)

    check = splunk_metric_check_second_run
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

    check = splunk_metric_check_third_run
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


@pytest.mark.unit
def test_splunk_empty_metrics(splunk_empty_metrics, telemetry):
    check = splunk_empty_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(0)
    telemetry.assert_metric("metric_name", count=0)


@pytest.mark.unit
def test_splunk_minimal_metrics(splunk_minimal_metrics, telemetry):
    check = splunk_minimal_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)

    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1488974400.0)


@pytest.mark.unit
def test_splunk_partially_incomplete_metrics(splunk_partially_incomplete_metrics, telemetry, aggregator):
    check = splunk_partially_incomplete_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(1)

    telemetry.assert_metric("metric_name", count=1, value=1.0, tags=[], hostname='', timestamp=1488974400.0)

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 3  # TODO: Melcom - Verify this changed from 1 to 3 - 2 of 3 is empty messages
    assert service_checks[0].status == AgentCheck.WARNING
    assert service_checks[0].message == \
           "The saved search 'partially_incomplete_metrics' contained 1 incomplete records"


@pytest.mark.unit
def test_splunk_full_metrics(splunk_full_metrics, telemetry, aggregator):
    check = splunk_full_metrics
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


# TODO: Melcom - Error - Missing 'value' field in result data
@pytest.mark.unit
def test_splunk_alternative_fields_metrics(splunk_alternative_fields_metrics, telemetry, aggregator):
    check = splunk_alternative_fields_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1488974400.0)


# TODO: Melcom - Error - Missing 'value' field in result data
@pytest.mark.unit
def test_splunk_fixed_metric_name(splunk_fixed_metric_name, telemetry, aggregator):
    check = splunk_fixed_metric_name
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("custommetric", count=2, value=3.0, tags=["mymetric:metric_name"], hostname='',
                            timestamp=1488974400.0)


# TODO: Melcom - Error - Missing 'value' field in result data
@pytest.mark.unit
def test_splunk_warning_on_missing_fields(splunk_warning_on_missing_fields, telemetry, aggregator):
    check = splunk_warning_on_missing_fields
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.WARNING, \
        "service check should have status AgentCheck.WARNING when fields are missing"


@pytest.mark.unit
def test_splunk_same_data_metrics(splunk_same_data_metrics, telemetry, aggregator):
    check = splunk_same_data_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=2.0, tags=[], hostname='',
                            timestamp=1488974400.0)



@pytest.mark.unit
def test_splunk_earliest_time_and_duplicates(splunk_earliest_time_and_duplicates_first_run,
                                             splunk_earliest_time_and_duplicates_second_run,
                                             splunk_earliest_time_and_duplicates_third_run,
                                             telemetry, aggregator):
    # Initial run
    check, test_data = splunk_earliest_time_and_duplicates_first_run

    test_data["sid"] = "poll"
    test_data["time"] = time_to_seconds("2017-03-08T18:29:59.000000+0000")
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(4)

    telemetry.assert_metric("name", count=4, value=66.0, tags=[], hostname='')
    telemetry.assert_metric("name", count=1, value=11.0, tags=[], hostname='', timestamp=1488997796.0)
    telemetry.assert_metric("name", count=1, value=12.0, tags=[], hostname='', timestamp=1488997797.0)
    telemetry.assert_metric("name", count=1, value=21.0, tags=[], hostname='', timestamp=1488997798.0)
    telemetry.assert_metric("name", count=1, value=22.0, tags=[], hostname='', timestamp=1488997799.0)
    telemetry.reset()  # TODO: Melcom - Is a reset correct for the next run
    aggregator.reset()  # TODO: Melcom - Is a reset correct for the next run

    # Respect earliest_time
    check, test_data = splunk_earliest_time_and_duplicates_second_run

    test_data["sid"] = "poll1"
    test_data["earliest_time"] = '2017-03-08T18:30:00.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)

    telemetry.assert_metric("name", count=2, value=53.0, tags=[], hostname='')
    telemetry.assert_metric("name", count=1, value=22.0, tags=[], hostname='', timestamp=1488997799.0)
    telemetry.assert_metric("name", count=1, value=31.0, tags=[], hostname='', timestamp=1488997800.0)
    telemetry.reset()  # TODO: Melcom - Is a reset correct for the next run
    aggregator.reset()  # TODO: Melcom - Is a reset correct for the next run

    # Throw exception during search
    check, test_data = splunk_earliest_time_and_duplicates_third_run

    test_data["throw"] = True
    check_response = check.run()

    assert check_response != '', "The check run cycle should produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "service check should have status AgentCheck.CRITICAL"


@pytest.mark.unit
def test_splunk_delay_first_time(splunk_delay_first_time_first_run,
                                 splunk_delay_first_time_second_run,
                                 splunk_delay_first_time_third_run, telemetry, aggregator):

    # Initial run
    check, test_data = splunk_delay_first_time_first_run
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(0)

    # Not polling yet
    check, test_data = splunk_delay_first_time_second_run

    test_data["time"] = 30  # Set Current Time
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(0)

    # Polling
    # TODO: Melcom - current_time_seconds >= self.launch_time_seconds + self.initial_delay_seconds
    # self.launch_time_seconds has the same time as current_time_seconds so this will always be false
    check, test_data = splunk_delay_first_time_third_run

    test_data["time"] = 62  # Set Current Time
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2)


@pytest.mark.unit
def test_splunk_continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric, telemetry, aggregator):
    check, test_data = splunk_continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric)

    # Initial run with initial time
    test_data["time"] = time_to_seconds('2017-03-08T00:00:00.000000+0000')
    test_data["earliest_time"] = '2017-03-08T00:00:00.000000+0000'
    test_data["latest_time"] = None

    check_response = check.run()
    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(0)

    test_data["time"] = time_to_seconds('2017-03-08T01:00:05.000000+0000')
    for slice_num in range(0, 12):
        telemetry.reset()
        aggregator.reset()

        test_data["earliest_time"] = '2017-03-08T00:%s:01.000000+0000' % (str(slice_num * 5).zfill(2))
        test_data["latest_time"] = '2017-03-08T00:%s:01.000000+0000' % (str((slice_num + 1) * 5).zfill(2))
        if slice_num == 11:
            test_data["latest_time"] = '2017-03-08T01:00:01.000000+0000'

        check, test_data = splunk_continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric)
        check_response = check.run()
        service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

        telemetry.assert_total_metrics(0)

        assert check_response == '', "The check run cycle should not produce a error"
        assert check.continue_after_commit is True
        assert len(service_checks) == 2
        assert service_checks[0].status == AgentCheck.OK

    telemetry.reset()
    aggregator.reset()

    # Now continue with real-time polling (the earliest time taken from last event or last restart chunk)
    test_data["earliest_time"] = '2017-03-08T01:00:01.000000+0000'
    test_data["latest_time"] = None

    check, test_data = splunk_continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric)
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"
    assert check.continue_after_commit is False, "As long as we are not done with history, the check should continue"



# TODO
@pytest.mark.unit
def test_splunk_query_initial_history(splunk_query_initial_history, telemetry, aggregator):
    check = splunk_query_initial_history
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_max_restart_time(splunk_max_restart_time, telemetry, aggregator):
    check = splunk_max_restart_time
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_keep_time_on_failure(splunk_keep_time_on_failure, telemetry, aggregator):
    check = splunk_keep_time_on_failure
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_advance_time_on_success(splunk_advance_time_on_success, telemetry, aggregator):
    check = splunk_advance_time_on_success
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_wildcard_searches(splunk_wildcard_searches, telemetry, aggregator):
    check = splunk_wildcard_searches
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_saved_searches_error(splunk_saved_searches_error, telemetry, aggregator):
    check = splunk_saved_searches_error
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_saved_searches_ignore_error(splunk_saved_searches_ignore_error, telemetry, aggregator):
    check = splunk_saved_searches_ignore_error
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metric_individual_dispatch_failures(splunk_metric_individual_dispatch_failures, telemetry, aggregator):
    check = splunk_metric_individual_dispatch_failures
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metric_individual_search_failures(splunk_metric_individual_search_failures, telemetry, aggregator):
    check = splunk_metric_individual_search_failures
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metric_search_full_failure(splunk_metric_search_full_failure, telemetry, aggregator):
    check = splunk_metric_search_full_failure
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metric_respect_parallel_dispatches(splunk_metric_respect_parallel_dispatches, telemetry, aggregator):
    check = splunk_metric_respect_parallel_dispatches
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_selective_fields_for_identification(splunk_selective_fields_for_identification, telemetry, aggregator):
    check = splunk_selective_fields_for_identification
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_all_fields_for_identification(splunk_all_fields_for_identification, telemetry, aggregator):
    check = splunk_all_fields_for_identification
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_all_fields_for_identification_backward_compatibility(
        splunk_all_fields_for_identification_backward_compatibility, telemetry, aggregator):
    check = splunk_all_fields_for_identification_backward_compatibility
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


@pytest.mark.unit
def test_splunk_checks_backward_compatibility_new_conf(splunk_checks_backward_compatibility_new_conf,
                                                       telemetry, aggregator):
    check = splunk_checks_backward_compatibility_new_conf
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1923825600)

    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"


@pytest.mark.unit
def test_splunk_default_parameters(splunk_default_parameters, telemetry, aggregator):
    check = splunk_default_parameters
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)


@pytest.mark.unit
def test_splunk_non_default_parameters(splunk_non_default_parameters, telemetry, aggregator):
    check = splunk_non_default_parameters
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)


@pytest.mark.unit
def test_splunk_overwrite_default_parameters(splunk_overwrite_default_parameters, telemetry, aggregator):
    check = splunk_overwrite_default_parameters
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)


@pytest.mark.unit
def test_splunk_config_max_query_chunk_sec_history(splunk_config, splunk_instance_basic_auth, mock_splunk_metric,
                                                   telemetry, aggregator):
    check, test_data = splunk_config_max_query_chunk_sec_history(splunk_config, splunk_instance_basic_auth,
                                                                 mock_splunk_metric)

    test_data["time"] = time_to_seconds('2017-03-09T00:00:00.000000+0000')
    test_data["earliest_time"] = '2017-03-08T00:00:00.000000+0000'

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(1)

    last_observed_timestamp = telemetry.metrics("metric_name")[0].timestamp
    # TODO: Melcom - last_observed_timestamp is not correct
    assert last_observed_timestamp == time_to_seconds('2017-03-08T00:04:59.000000+0000')

    check, test_data = splunk_config_max_query_chunk_sec_history(splunk_config, splunk_instance_basic_auth,
                                                                 mock_splunk_metric)

    test_data["time"] = time_to_seconds('2017-03-08T12:00:00.000000+0000')
    test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)  # TODO: Melcom - How can this be two if the file only has 1 in

    last_observed_timestamp = telemetry.metrics("metric_name")[0].timestamp
    # TODO: Melcom - last_observed_timestamp is not correct
    assert last_observed_timestamp == time_to_seconds('2017-03-08T11:04:59.000000+0000')


@pytest.mark.unit
def test_splunk_config_max_query_chunk_sec_live(splunk_config_max_query_chunk_sec_live, telemetry, aggregator):
    check, test_data = splunk_config_max_query_chunk_sec_live

    # Initial run with initial history time
    test_data["time"] = time_to_seconds('2017-03-08T11:58:00.000000+0000')
    test_data["earliest_time"] = '2017-03-08T11:58:00.000000+0000'

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)  # TODO: Melcom - How can this be two if the file only has 1 in

    last_observed_timestamp = telemetry.metrics("metric_name")[0].timestamp
    # TODO: Melcom - last_observed_timestamp is not correct
    assert last_observed_timestamp == time_to_seconds('2017-03-08T12:00:00.000000+0000')


@pytest.mark.unit
def test_splunk_metrics_with_token_auth_with_valid_token(splunk_metrics_with_token_auth_with_valid_token, telemetry,
                                                         aggregator):
    check = splunk_metrics_with_token_auth_with_valid_token
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", value=3.0, tags=[], timestamp=1488974400.0)

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 2
    assert service_checks[0].status == AgentCheck.OK


@pytest.mark.unit
def test_splunk_metrics_with_token_auth_with_invalid_token(splunk_metrics_with_token_auth_with_invalid_token, telemetry,
                                                           aggregator):
    check = splunk_metrics_with_token_auth_with_invalid_token
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL
    assert service_checks[0].message == "Current in use authentication token is expired. Please provide a valid token" \
                                        " in the YAML and restart the Agent"


@pytest.mark.unit
def test_splunk_metrics_with_token_auth_audience_param_not_set(splunk_metrics_with_token_auth_audience_param_not_set,
                                                               telemetry, aggregator):
    check = splunk_metrics_with_token_auth_audience_param_not_set
    check_response = check.run()

    assert check_response != '', "The check run cycle SHOULD produce a error."

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "Splunk metric instance missing " \
                                                            "'authentication.token_auth.audience' value"


@pytest.mark.unit
def test_splunk_metrics_with_token_auth_name_param_not_set(splunk_metrics_with_token_auth_name_param_not_set,
                                                           telemetry,
                                                           aggregator):
    check = splunk_metrics_with_token_auth_name_param_not_set
    check_response = check.run()

    assert check_response != '', "The check run cycle SHOULD produce a error."

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "Splunk metric instance missing " \
                                                            "'authentication.token_auth.name' value"


@pytest.mark.unit
def test_splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth(
        splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth, telemetry, aggregator):
    check = splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", value=3.0, tags=[], timestamp=1488974400.0)

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 2
    assert service_checks[0].status == AgentCheck.OK


@pytest.mark.unit
def test_splunk_metrics_with_token_auth_memory_token_expired(splunk_metrics_with_token_auth_memory_token_expired,
                                                             telemetry, aggregator):
    check = splunk_metrics_with_token_auth_memory_token_expired
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL
    assert service_checks[0].message == "Current in use authentication token is expired. Please provide a valid token" \
                                        " in the YAML and restart the Agent"

    check_response = check.run()
