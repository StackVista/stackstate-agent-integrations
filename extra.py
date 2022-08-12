

# @pytest.mark.unit
# def test_splunk_config_max_query_chunk_sec_live(splunk_config_max_query_chunk_sec_live):
#     # type: (str) -> None
#
#     assert splunk_config_max_query_chunk_sec_live == ''
#     telemetry.assert_total_metrics(1)
#     telemetry.assert_metric("metric_name", count=1, value=120.0, tags=['checktag:checktagvalue'], hostname='',
#                             timestamp=1488931320.0)
#
#     print("transaction._transactions")
#     print(transaction._transactions)
#     print("transaction._transaction_steps")
#     print(transaction._transaction_steps)
#     print("transaction._transactions")
#     print(state._state)
#
#     assert 1 == 2
#     # TODO:
#     # self.check.status.data.get('http://localhost:13001').get('metrics')
#     # TODO:
#     # self.assertEqual(last_observed_timestamp, time_to_seconds('2017-03-08T12:00:00.000000+0000'))


# TODO: Example
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