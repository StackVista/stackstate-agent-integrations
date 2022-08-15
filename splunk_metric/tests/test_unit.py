# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.state_common import generate_state_key


@pytest.mark.unit
def test_splunk_error_response(splunk_error_response_check, aggregator):
    check = splunk_error_response_check
    check_response = check.run()

    assert check_response != '', "The check run cycle should run a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1  # TODO: Verify this changed from 2 to 1
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

    telemetry.assert_metric("metric_name", count=0)


@pytest.mark.unit
def test_splunk_minimal_metrics(splunk_minimal_metrics, telemetry):
    check = splunk_minimal_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1488974400.0)


@pytest.mark.unit
def test_splunk_partially_incomplete_metrics(splunk_partially_incomplete_metrics, telemetry, aggregator):
    check = splunk_partially_incomplete_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("metric_name", count=1, value=1.0, tags=[], hostname='', timestamp=1488974400.0)

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 3  # TODO: Verify this changed from 1 to 3 - 2 of 3 is empty messages
    assert service_checks[0].status == AgentCheck.WARNING
    assert service_checks[0].message == \
           "The saved search 'partially_incomplete_metrics' contained 1 incomplete records"


@pytest.mark.unit
def test_splunk_full_metrics(splunk_full_metrics, telemetry, aggregator):
    check = splunk_full_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("metric_name", count=1, value=1.0, tags=[
                'hostname:myhost',
                'some:tag',
                'checktag:checktagvalue'], hostname='', timestamp=1488997796.0)

    telemetry.assert_metric("metric_name", count=1, value=1.0, tags=[
                'hostname:123',
                'some:123',
                'device_name:123',
                'checktag:checktagvalue'], hostname='', timestamp=1488997797.0)


# TODO ERROR:
@pytest.mark.unit
def test_splunk_alternative_fields_metrics(splunk_alternative_fields_metrics, telemetry, aggregator):
    check = splunk_alternative_fields_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[], hostname='', timestamp=1488974400.0)


@pytest.mark.unit
def test_splunk_fixed_metric_name(splunk_fixed_metric_name, telemetry, aggregator):
    check = splunk_fixed_metric_name
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("custommetric", count=2, value=3.0, tags=["mymetric:metric_name"], hostname='',
                            timestamp=1488974400.0)


@pytest.mark.unit
def test_splunk_warning_on_missing_fields(splunk_warning_on_missing_fields, telemetry, aggregator):
    check = splunk_warning_on_missing_fields
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


@pytest.mark.unit
def test_splunk_same_data_metrics(splunk_same_data_metrics, telemetry, aggregator):
    check = splunk_same_data_metrics
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    telemetry.assert_metric("metric_name", count=2, value=2.0, tags=[], hostname='',
                            timestamp=1488974400.0)


@pytest.mark.unit
def test_splunk_earliest_time_and_duplicates(splunk_earliest_time_and_duplicates, telemetry, aggregator):
    check = splunk_earliest_time_and_duplicates
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    # test_mocks = {
    #     '_auth_session': _mocked_auth_session,
    #     '_dispatch': _mocked_dispatch_saved_search_dispatch,
    #     '_search': _mocked_polling_search,
    #     '_current_time_seconds': _mocked_current_time_seconds,
    #     '_saved_searches': _mocked_saved_searches,
    #     '_finalize_sid': _mocked_finalize_sid_none
    # }

    # # Initial run
    # test_data["sid"] = "poll"
    # test_data["time"] = time_to_seconds("2017-03-08T18:29:59.000000+0000")
    # self.run_check(config, mocks=test_mocks)
    # self.assertEqual(len(self.metrics), 4)
    # self.assertEqual([e[2] for e in self.metrics], [11, 12, 21, 22])

    # # respect earliest_time
    # test_data["sid"] = "poll1"
    # test_data["earliest_time"] = '2017-03-08T18:30:00.000000+0000'
    # self.run_check(config, mocks=test_mocks)
    # self.assertEqual(len(self.metrics), 1)
    # self.assertEqual([e[2] for e in self.metrics], [31])

    # # Throw exception during search
    # test_data["throw"] = True
    # thrown = False
    # try:
    #     self.run_check(config, mocks=test_mocks)
    # except CheckException:
    #     thrown = True
    # self.assertTrue(thrown, "Expect thrown to be done from the mocked search")
    # self.assertEquals(self.service_checks[1]['status'], 2, "service check should have status AgentCheck.CRITICAL")

    assert False  # TODO


@pytest.mark.unit
def test_splunk_delay_first_time(splunk_delay_first_time, telemetry, aggregator):
    check = splunk_delay_first_time
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_continue_after_restart(splunk_continue_after_restart, telemetry, aggregator):
    check = splunk_continue_after_restart
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


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


# TODO
@pytest.mark.unit
def test_splunk_all_fields_for_identification_backward_compatibility_new_conf(
        splunk_all_fields_for_identification_backward_compatibility_new_conf, telemetry, aggregator):
    check = splunk_all_fields_for_identification_backward_compatibility_new_conf
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_default_parameters(splunk_default_parameters, telemetry, aggregator):
    check = splunk_default_parameters
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_non_default_parameters(splunk_non_default_parameters, telemetry, aggregator):
    check = splunk_non_default_parameters
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_overwrite_default_parameters(splunk_overwrite_default_parameters, telemetry, aggregator):
    check = splunk_overwrite_default_parameters
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_config_max_query_chunk_sec_history(splunk_config_max_query_chunk_sec_history, telemetry, aggregator):
    check = splunk_config_max_query_chunk_sec_history
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_config_max_query_chunk_sec_live(splunk_config_max_query_chunk_sec_live, telemetry, aggregator):
    check = splunk_config_max_query_chunk_sec_live
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metrics_with_token_auth_with_valid_token(splunk_metrics_with_token_auth_with_valid_token, telemetry,
                                                         aggregator):
    check = splunk_metrics_with_token_auth_with_valid_token
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metrics_with_token_auth_with_invalid_token(splunk_metrics_with_token_auth_with_invalid_token, telemetry,
                                                           aggregator):
    check = splunk_metrics_with_token_auth_with_invalid_token
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metrics_with_token_auth_audience_param_not_set(splunk_metrics_with_token_auth_audience_param_not_set,
                                                               telemetry, aggregator):
    check = splunk_metrics_with_token_auth_audience_param_not_set
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metrics_with_token_auth_name_param_not_set(splunk_metrics_with_token_auth_name_param_not_set, telemetry,
                                                           aggregator):
    check = splunk_metrics_with_token_auth_name_param_not_set
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth(
        splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth, telemetry, aggregator):
    check = splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO


# TODO
@pytest.mark.unit
def test_splunk_metrics_with_token_auth_memory_token_expired(splunk_metrics_with_token_auth_memory_token_expired,
                                                             telemetry, aggregator):
    check = splunk_metrics_with_token_auth_memory_token_expired
    check_response = check.run()

    assert check_response == '', "The check run cycle should not produce a error"

    assert False  # TODO



