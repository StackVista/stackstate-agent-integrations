# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time

# TODO: TestSplunkQueryInitialHistory

import pytest

from freezegun import freeze_time
from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.state_common import generate_state_key
from stackstate_checks.splunk.config.splunk_instance_config import time_to_seconds
from .conftest import continue_after_restart


@pytest.mark.unit
def test_error_response(error_response_check, telemetry, aggregator):
    check = error_response_check
    check_response = check.run()

    assert check_response != '', "The check run cycle should run a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    telemetry.assert_total_metrics(0)

    assert len(service_checks) == 1  # TODO: Melcom - Verify this changed from 2 to 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "service check should have status AgentCheck.CRITICAL"


@pytest.mark.unit
def test_metric_check(metric_check_first_run, metric_check_second_run,
                             metric_check_third_run, transaction, state):

    check = metric_check_first_run
    check_response = check.run()
    assert check_response == '', "The check run should not return a error"

    persistent_state_key = generate_state_key(check._get_instance_key().to_string(), check.PERSISTENT_CACHE_KEY)
    first_transaction = transaction._transactions.get(check.check_id)
    first_state = state.get_state(check, check.check_id, persistent_state_key)

    transaction.assert_started_transaction(check.check_id, False)
    transaction.assert_stopped_transaction(check.check_id, True)
    transaction.assert_discarded_transaction(check.check_id, False)

    check = metric_check_second_run
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

    check = metric_check_third_run
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
def test_empty_metrics(empty_metrics, telemetry):
    check = empty_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(0)
    telemetry.assert_metric("metric_name", count=0)


@pytest.mark.unit
def test_minimal_metrics(minimal_metrics, telemetry):
    check = minimal_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)

    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1488974400.0)


@pytest.mark.unit
def test_partially_incomplete_metrics(partially_incomplete_metrics, telemetry, aggregator):
    check = partially_incomplete_metrics
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
def test_full_metrics(full_metrics, telemetry, aggregator):
    check = full_metrics
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
def test_alternative_fields_metrics(alternative_fields_metrics, telemetry, aggregator):
    check = alternative_fields_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    # telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1488974400.0)


# TODO: Melcom - Error - Missing 'value' field in result data
@pytest.mark.unit
def test_fixed_metric_name(fixed_metric_name, telemetry, aggregator):
    check = fixed_metric_name
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("custommetric", count=2, value=3.0, tags=["mymetric:metric_name"], hostname='',
                            timestamp=1488974400.0)


# TODO: Melcom - Error - Missing 'value' field in result data
@pytest.mark.unit
def test_warning_on_missing_fields(warning_on_missing_fields, telemetry, aggregator):
    check = warning_on_missing_fields
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.WARNING, \
        "service check should have status AgentCheck.WARNING when fields are missing"


@pytest.mark.unit
def test_same_data_metrics(same_data_metrics, telemetry, aggregator):
    check = same_data_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=2.0, tags=[], hostname='',
                            timestamp=1488974400.0)



@pytest.mark.unit
def test_earliest_time_and_duplicates(earliest_time_and_duplicates_first_run,
                                             earliest_time_and_duplicates_second_run,
                                             earliest_time_and_duplicates_third_run,
                                             telemetry, aggregator):
    # Initial run
    check, test_data = earliest_time_and_duplicates_first_run

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
    check, test_data = earliest_time_and_duplicates_second_run

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
    check, test_data = earliest_time_and_duplicates_third_run

    test_data["throw"] = True
    check_response = check.run()

    assert check_response != '', "The check run cycle should produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "service check should have status AgentCheck.CRITICAL"


@pytest.mark.unit
def test_delay_first_time(delay_first_time_first_run,
                                 delay_first_time_second_run,
                                 delay_first_time_third_run, telemetry, aggregator):

    # Initial run
    check, test_data = delay_first_time_first_run
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(0)

    # Not polling yet
    check, test_data = delay_first_time_second_run

    test_data["time"] = 30  # Set Current Time
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(0)

    # Polling
    # TODO: Melcom - current_time_seconds >= self.launch_time_seconds + self.initial_delay_seconds
    # self.launch_time_seconds has the same time as current_time_seconds so this will always be false
    check, test_data = delay_first_time_third_run

    test_data["time"] = 62  # Set Current Time
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2)


# Busy
@pytest.mark.unit
def test_continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric, telemetry, aggregator):
    check, test_data = continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric)

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

        check, test_data = continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric)
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

    check, test_data = continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric)
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"
    assert check.continue_after_commit is False, "As long as we are not done with history, the check should continue"


# TODO: Melcom - Contains a error
@pytest.mark.unit
@freeze_time("2017-03-09T00:00:00.000000+0000")
def test_query_initial_history(query_initial_history, telemetry, aggregator):
    check, test_data = query_initial_history

    # Gather initial data
    for slice_num in range(0, 23):
        test_data["earliest_time"] = '2017-03-08T%s:00:00.000000+0000' % (str(slice_num).zfill(2))
        test_data["latest_time"] = '2017-03-08T%s:00:00.000000+0000' % (str(slice_num + 1).zfill(2))
        check.run()
        assert check.continue_after_commit is True, "As long as we are not done with history, the check should continue"

    # Now continue with real-time polling (earliest time taken from last event)
    test_data["earliest_time"] = '2017-03-08T23:00:00.000000+0000'
    test_data["latest_time"] = None
    check.run()

    telemetry.assert_total_metrics(2)
    assert check.continue_after_commit is True, "As long as we are not done with history, the check should continue"


# Done
@pytest.mark.unit
def test_max_restart_time(max_restart_time, telemetry, aggregator):
    check, test_data = max_restart_time

    with freeze_time("2017-03-09T00:00:00.000000+0000"):
        test_data["earliest_time"] = '2017-03-08T00:00:00.000000+0000'
        check_response = check.run()

        assert check_response == '', "The check run cycle SHOULD NOT produce a error"
        telemetry.assert_total_metrics(0)

    with freeze_time("2017-03-08T12:00:00.000000+0000"):
        test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'
        test_data["latest_time"] = '2017-03-08T11:00:00.000000+0000'
        check_response = check.run()

        assert check_response == '', "The check run cycle SHOULD NOT produce a error"
        telemetry.assert_total_metrics(0)


# Done
@pytest.mark.unit
@freeze_time("2017-03-08T11:00:00.000000+0000")
def test_keep_time_on_failure(keep_time_on_failure, telemetry, aggregator):
    check, test_data = keep_time_on_failure

    test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    telemetry.assert_total_metrics(2)

    test_data["earliest_time"] = '2017-03-08T12:00:01.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"


# Done
@pytest.mark.unit
@freeze_time("2017-03-08T11:00:00.000000+0000")
def test_advance_time_on_success(advance_time_on_success, telemetry, aggregator):
    check, test_data = advance_time_on_success

    test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    telemetry.assert_total_metrics(2)

    test_data["earliest_time"] = '2017-03-08T12:00:01.000000+0000'
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"


# Done
@pytest.mark.unit
def test_wildcard_searches(wildcard_searches, telemetry, aggregator):
    check, data = wildcard_searches

    data['saved_searches'] = ["minimal_metrics", "blaat"]
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    telemetry.assert_total_metrics(2)
    assert len(check.instance_data.saved_searches.searches) == 1

    telemetry.reset()

    data['saved_searches'] = []
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"
    telemetry.assert_total_metrics(0)
    assert len(check.instance_data.saved_searches.searches) == 0


# Done
@pytest.mark.unit
def test_saved_searches_error(saved_searches_error, telemetry, aggregator):
    check = saved_searches_error
    check_response = check.run()

    assert check_response != '', "The check run cycle SHOULD produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert service_checks[0].status == AgentCheck.CRITICAL, "service check should have status AgentCheck.CRITICAL"
    assert service_checks[0].message == "Boom"


# Done
@pytest.mark.unit
def test_saved_searches_ignore_error(saved_searches_ignore_error, telemetry, aggregator):
    check = saved_searches_ignore_error
    check_response = check.run()

    assert check_response == '', "The check run cycle NOT SHOULD produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert service_checks[0].status == AgentCheck.CRITICAL, "service check should have status AgentCheck.CRITICAL"
    assert service_checks[0].message == "Boom"


# TODO: Melcom - There is no metric error for the BOOM
@pytest.mark.unit
def test_individual_dispatch_failures(individual_dispatch_failures, telemetry, aggregator):
    check = individual_dispatch_failures
    check_response = check.run()

    assert check_response == '', "The check run cycle NOT SHOULD produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, timestamp=1488974400.0)

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 3

    assert service_checks[0].status == AgentCheck.WARNING
    assert service_checks[0].message == \
           "Failed to execute dispatched search 'full_metrics' with id full_metrics due to: BOOM"


# TODO: Melcom - There is no metric error for the BOOM
@pytest.mark.unit
def test_individual_search_failures(individual_search_failures, telemetry, aggregator):
    check = individual_search_failures
    check_response = check.run()

    assert check_response == '', "The check run cycle NOT SHOULD produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, timestamp=1488974400.0)

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 3

    assert service_checks[0].status == AgentCheck.WARNING
    assert service_checks[0].message == \
           "Failed to execute dispatched search 'full_metrics' with id full_metrics due to: BOOM"


# Done
@pytest.mark.unit
def test_search_full_failure(search_full_failure, telemetry, aggregator):
    check = search_full_failure

    check_response = check.run()
    assert check_response != '', "The check run cycle SHOULD produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert service_checks[0].status == AgentCheck.CRITICAL
    assert service_checks[0].message == "No saved search was successfully executed."


# Done
@pytest.mark.unit
def test_respect_parallel_dispatches(respect_parallel_dispatches, telemetry, aggregator):
    check = respect_parallel_dispatches

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    assert check.parallel_dispatches_failed is False, "The check should pass parallel dispatches"


# Done
@pytest.mark.unit
def test_selective_fields_for_identification_check(selective_fields_for_identification_check, telemetry, aggregator):
    check = selective_fields_for_identification_check
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

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)
    telemetry.assert_total_metrics(0)

    assert service_checks[2].status == AgentCheck.OK


# Done
@pytest.mark.unit
def test_all_fields_for_identification_check(all_fields_for_identification_check, telemetry, aggregator):
    check = all_fields_for_identification_check
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], timestamp=1923825600)

    # Remove the existing metrics to evaluate what the next run gives
    telemetry.reset()

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)
    telemetry.assert_total_metrics(0)

    assert service_checks[2].status == AgentCheck.OK


# Done
@pytest.mark.unit
def test_backward_compatibility(backward_compatibility_check, telemetry, aggregator):
    check = backward_compatibility_check
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], timestamp=1923825600)

    # Remove the existing metrics to evaluate what the next run gives
    telemetry.reset()

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)
    telemetry.assert_total_metrics(0)

    assert service_checks[2].status == AgentCheck.OK


# Done
@pytest.mark.unit
def test_backward_compatibility_new_conf(backward_compatibility_new_conf_check, telemetry, aggregator):
    check = backward_compatibility_new_conf_check
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], timestamp=1923825600)

    # Remove the existing metrics to evaluate what the next run gives
    telemetry.reset()

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)
    telemetry.assert_total_metrics(0)

    assert service_checks[2].status == AgentCheck.OK


# Done
@pytest.mark.unit
def test_default_parameters(default_parameters_check, telemetry, aggregator):
    check = default_parameters_check
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error"

    telemetry.assert_total_metrics(2)


# Done
@pytest.mark.unit
def test_non_default_parameters(non_default_parameters_check, telemetry, aggregator):
    check = non_default_parameters_check
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)


# Done
@pytest.mark.unit
def test_overwrite_default_parameters(overwrite_default_parameters_check, telemetry, aggregator):
    check = overwrite_default_parameters_check
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)


# Done
# TODO: Melcom - The last_observed_timestamp does not match what the original tests has and matches the actual file
@pytest.mark.unit
def test_max_query_chunk_sec_history(max_query_chunk_sec_history_check, telemetry):
    check, test_data = max_query_chunk_sec_history_check

    with freeze_time("2017-03-09T00:00:00.000000+0000"):
        test_data["earliest_time"] = '2017-03-08T00:00:00.000000+0000'

        check_response = check.run()
        assert check_response == '', "The check run cycle SHOULD NOT produce a error."

        telemetry.assert_total_metrics(1)

        last_observed_timestamp = telemetry.metrics("metric_name")[0].timestamp
        assert last_observed_timestamp == time_to_seconds('2017-03-08T00:04:59.000000+0000')

    with freeze_time("2017-03-08T12:00:00.000000+0000"):
        test_data["earliest_time"] = '2017-03-08T11:00:00.000000+0000'
        check_response = check.run()

        assert check_response == '', "The check run cycle SHOULD NOT produce a error."

        telemetry.assert_total_metrics(2)

        last_observed_timestamp = telemetry.metrics("metric_name")[0].timestamp
        assert last_observed_timestamp == time_to_seconds('2017-03-08T11:04:59.000000+0000')


# Done
# TODO: Melcom - Last Time Assert Does Not Match
@pytest.mark.unit
@freeze_time("2017-03-08T11:58:00.000000+0000")
def test_max_query_chunk_sec_live(max_query_chunk_sec_live_check, telemetry, aggregator):
    check = max_query_chunk_sec_live_check

    check_response = check.run()
    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(1)

    last_observed_timestamp = telemetry.metrics("metric_name")[0].timestamp
    assert last_observed_timestamp == time_to_seconds('2017-03-08T12:00:00.000000+0000')


# Done
@pytest.mark.unit
def test_token_auth_with_valid_token(token_auth_with_valid_token_check, telemetry, aggregator):
    check = token_auth_with_valid_token_check
    check_response = check.run()

    assert check_response == '', "The check run cycle SHOULD NOT produce a error."

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", value=3.0, tags=[], timestamp=1488974400.0)

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 3
    assert service_checks[0].status == AgentCheck.OK

    assert service_checks[2].status == AgentCheck.OK
    assert service_checks[2].message == check.CHECK_NAME + " check was processed successfully"


# Done
@pytest.mark.unit
def test_authentication_invalid_token(authentication_invalid_token_check, telemetry, aggregator):
    check = authentication_invalid_token_check
    check_response = check.run()

    assert check_response == '', "The check SHOULD NOT return a error result after running."

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 2
    assert service_checks[0].status == AgentCheck.CRITICAL
    assert service_checks[0].message == "Current in use authentication token is expired. Please provide a valid token" \
                                        " in the YAML and restart the Agent"


# Done
@pytest.mark.unit
def test_authentication_token_no_audience_parameter_check(authentication_token_no_audience_parameter_check, telemetry,
                                                          aggregator):
    check = authentication_token_no_audience_parameter_check
    check_response = check.run()

    assert check_response != '', "The check SHOULD return a error result after running."

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "Splunk metric instance missing " \
                                                            "'authentication.token_auth.audience' value"
    assert service_checks[0].message == "Instance missing \"authentication.token_auth.audience\" value"


# Done
@pytest.mark.unit
def test_authentication_token_no_name_parameter_check(authentication_token_no_name_parameter_check, telemetry,
                                                      aggregator):
    check = authentication_token_no_name_parameter_check
    check_response = check.run()

    assert check_response != '', "The check SHOULD return a error result after running."

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "Splunk metric instance missing " \
                                                            "'authentication.token_auth.name' value"
    assert service_checks[0].message == "Instance missing \"authentication.token_auth.name\" value"


# Done
@pytest.mark.unit
def test_authentication_prefer_token_over_basic_check(authentication_prefer_token_over_basic_check, telemetry,
                                                      aggregator):
    check = authentication_prefer_token_over_basic_check
    check_response = check.run()

    assert check_response == '', "The check SHOULD NOT return a error result after running."

    telemetry.assert_total_metrics(2)
    telemetry.assert_metric("metric_name", value=3.0, tags=[], timestamp=1488974400.0)

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 3
    assert service_checks[0].status == AgentCheck.OK


# Done
@pytest.mark.unit
def test_authentication_token_expired_check(authentication_token_expired_check, telemetry, aggregator):
    check = authentication_token_expired_check
    check_response = check.run()

    assert check_response == '', "The check SHOULD NOT return a error result after running."

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 2
    assert service_checks[0].status == AgentCheck.CRITICAL
    assert service_checks[0].message == "Current in use authentication token is expired. Please provide a valid token" \
                                        " in the YAML and restart the Agent"

    assert service_checks[1].status == AgentCheck.OK
    assert service_checks[1].message == check.CHECK_NAME + " check was processed successfully"
