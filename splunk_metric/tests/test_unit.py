# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest

from stackstate_checks.base import AgentCheck


@pytest.mark.unit
def test_splunk_error_response(splunk_error_response_check, aggregator):
    check = splunk_error_response_check
    check_response = check.run()

    assert check_response != '', "The check run cycle should run a error"

    service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)

    assert len(service_checks) == 1  # TODO: Melcom - Verify this changed from 2 to 1
    assert service_checks[0].status == AgentCheck.CRITICAL, "service check should have status AgentCheck.CRITICAL"


@pytest.mark.unit
def test_splunk_metric_check(splunk_metric_check, splunk_metric_check_second_run, transaction):
    print("================")

    check = splunk_metric_check
    check_response = check.run()
    assert check_response == '', "The check run should not return a error"

    print(transaction._transactions)

    check = splunk_metric_check_second_run
    check_response = check.run()
    assert check_response == '', "The check run should not return a error"

    print(transaction._transactions)

    print("================")
    assert 1 == 2

# Make sure that the transactional state was started and did not fail between runs
# transaction.assert_started_transaction(check.check_id, False)
# transaction.assert_stopped_transaction(check.check_id, True)
# transaction.assert_discarded_transaction_reason(check.check_id, None)
# transaction.assert_discarded_transaction(check.check_id, False)
