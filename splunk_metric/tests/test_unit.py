# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest

# from .common import HOST, PORT
# from stackstate_checks.base import AgentCheck
from stackstate_checks.base.stubs import telemetry, transaction, state
# aggregator, topology,
# from .mock import MockSplunkMetric

# Commented out while fixing bugs

# @pytest.mark.unit
# def test_splunk_metric(splunk_metric):  # type: (MockSplunkMetric) -> None
#     check = splunk_metric
#     assert check.run() == ''
#
#     # instance = config.get('instances')[0]
#     # persist_status_key = instance.get('url') + "minimal_metrics"
#     # self.run_check(config, mocks={
#     #     '_search': _mocked_search,
#     #     '_saved_searches': _mocked_saved_searches,
#     #     '_auth_session': _mocked_auth_session,
#     #     '_dispatch_saved_search': _mocked_dispatch_saved_search
#     # })
#     # first_persistent_data = self.check.status.data.get(persist_status_key)
#     # self.run_check(config, mocks={
#     #     '_search': _mocked_search,
#     #     '_saved_searches': _mocked_saved_searches,
#     #     '_auth_session': _mocked_auth_session,
#     #     '_dispatch_saved_search': _mocked_dispatch_saved_search,
#     #     '_finalize_sid': _mocked_finalize_sid_none
#     # }, force_reload=True)
#     # second_persistent_data = self.check.status.data.get(persist_status_key)
#     # self.assertEqual(first_persistent_data, second_persistent_data)
#     # def _mocked_finalize_sid_exception(*args, **kwargs):
#     #     raise FinalizeException(None, "Error occured")
#     # thrown = False
#     # try:
#     #     self.run_check(config, mocks={
#     #         '_search': _mocked_search,
#     #         '_saved_searches': _mocked_saved_searches,
#     #         '_auth_session': _mocked_auth_session,
#     #         '_dispatch_saved_search': _mocked_dispatch_saved_search,
#     #         '_finalize_sid': _mocked_finalize_sid_exception
#     #     }, force_reload=True)
#     # except CheckException:
#     #     thrown = True
#     # self.assertTrue(thrown)
#     # self.assertIsNotNone(self.check.status.data.get(persist_status_key))
#     # self.tear_down(instance.get('url'), "minimal_metrics")
#
#     assert 1 == 1
#
#

@pytest.mark.unit
def test_splunk_config_max_query_chunk_sec_live(splunk_config_max_query_chunk_sec_live):
    # type: (str) -> None

    assert splunk_config_max_query_chunk_sec_live == ''
    telemetry.assert_total_metrics(1)
    telemetry.assert_metric("metric_name", count=1, value=120.0, tags=['checktag:checktagvalue'], hostname='',
                            timestamp=1488931320.0)

    print("transaction._transactions")
    print(transaction._transactions)
    print("transaction._transaction_steps")
    print(transaction._transaction_steps)
    print("transaction._transactions")
    print(state._state)

    assert 1 == 2
    # TODO:
    # self.check.status.data.get('http://localhost:13001').get('metrics')
    # TODO:
    # self.assertEqual(last_observed_timestamp, time_to_seconds('2017-03-08T12:00:00.000000+0000'))


# @pytest.mark.unit
# def test_splunk_error_response(splunk_error_response):  # type: (MockSplunkMetric) -> None
#     check = splunk_error_response
#
#     check_response = check.run()
#     assert check_response != '', "Check should return a error"
#
#     service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)
#
#     assert len(service_checks) == 1  # TODO: Melcom - Verify this changed from 2 to 1
#     assert service_checks[0].status == AgentCheck.CRITICAL, "service check should have status AgentCheck.CRITICAL"
#
#
# @pytest.mark.unit
# def test_example(splunk_minimal_metrics):  # type: (MockSplunkMetric) -> None
#     check = splunk_minimal_metrics
#     assert check.run() == ''
#
#     topo = [topology.get_snapshot("splunk:http://%s:%s" % (HOST, PORT))]
#     components = topo[0]["components"]
#     relations = topo[0]["relations"]
#
#     telemetry.assert_metric("metric_name", count=2, value=3.0, tags=[])
#
#     topology.assert_component(
#         components,
#         "urn:agent-integration-instance:/stubbed.hostname:splunk:http://%s:%s" % (HOST, PORT),
#         "agent-integration-instance"
#     )
#
#     topology.assert_relation(relations,
#                              "urn:agent-integration:/stubbed.hostname:splunk",
#                              "urn:agent-integration-instance:/stubbed.hostname:splunk:http://%s:%s" % (HOST, PORT),
#                              "has")
#
#     service_checks = aggregator.service_checks(check.SERVICE_CHECK_NAME)
#     assert len(service_checks) > 0
#     assert service_checks[0].status == AgentCheck.OK
#
#     transaction.assert_transaction_state(check, check.check_id, "minimal_metrics", -1)
#     state.assert_state_is_empty(check)
#
