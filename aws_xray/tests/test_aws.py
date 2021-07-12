# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import os
import sys

import jsonpickle
import mock
from mock import patch

from stackstate_checks.aws_xray import AwsCheck
from stackstate_checks.aws_xray.aws_xray import AwsClient, MAX_TRACE_HISTORY_LIMIT, MAX_TRACE_HISTORY_BATCH_SIZE, Instance, State
from stackstate_checks.base import TopologyInstance

AWS_REGION = 'eu-west-1'
AWS_ACCOUNT = '672574731473'


def get_xray_traces():
    traces = get_file('get_xray_traces.json')
    return traces


class MockAwsClient:
    def __init__(self, instance):
        self.region = AWS_REGION

    @staticmethod
    def get_account_id():
        return AWS_ACCOUNT


class MockBrokenAwsClient(MockAwsClient):

    @staticmethod
    def get_account_id():
        raise Exception("some dummy error: could not get the account id")


def test_process_batch_traces(instance):
    instance = Instance(instance)
    check = AwsCheck('batch', {}, {}, [instance])
    xray_traces_batch = get_xray_traces()
    traces = check.process_batch_traces(xray_traces_batch)
    assert len(traces) == 3
    assert len(traces[0]) == 25
    assert len(traces[1]) == 25
    assert len(traces[2]) == 5


# def test_traces():
#     check = AwsCheck('test', {}, {})
#     aws_client = MockAwsClient({}, {})
#     check.region = aws_client.region
#     check.account_id = aws_client.get_account_id()
#     traces = check._process_xray_traces(aws_client)
#     print(sys.getsizeof(traces))
#
#     assert len(traces) == 2
#     assert len(traces[0]) == 25
#     assert len(traces[1]) == 25
#     assert len(traces[2]) == 5


def test_get_start_end_time_trace_normal_start(instance):
    instance = Instance(instance)
    check = AwsCheck('aws', {}, {}, [instance])
    check._current_time = mock.MagicMock(return_value=datetime.datetime.utcnow())
    last_trace_end_timestamp = check._current_time.return_value - datetime.timedelta(hours=MAX_TRACE_HISTORY_LIMIT)
    st, et = check.get_start_end_time_trace(instance)
    # since there is no state, default start time will be now - 3 hrs
    assert st == last_trace_end_timestamp
    # since diff is 3 hrs, we will process in batch with end time = start + MAX_TRACE_HISTORY_BATCH_SIZE
    assert et == last_trace_end_timestamp + datetime.timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)


def test_get_start_end_time_trace_lagging_15_mins(instance):
    instance = Instance(instance)
    check = AwsCheck('aws', {}, {}, [instance])
    check._current_time = mock.MagicMock(return_value=datetime.datetime.utcnow())
    instance.state = State({'last_processed_timestamp': check._current_time.return_value-datetime.timedelta(minutes=15)})
    last_trace_end_timestamp = instance.state.last_processed_timestamp + datetime.timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)
    st, et = check.get_start_end_time_trace(instance)
    # state holds a time 15 mins behind, so start time will be from state
    assert st == instance.state.last_processed_timestamp
    # since the time from state is still lagging behind more than MAX_TRACE_HISTORY_BATCH_SIZE but less than
    # MAX_TRACE_HISTORY_LIMIT, end time = last time from state + MAX_TRACE_HISTORY_BATCH_SIZE
    assert et == last_trace_end_timestamp


def test_get_start_end_time_trace_lagging_15_hrs(instance):
    instance = Instance(instance)
    check = AwsCheck('aws', {}, {}, [instance])
    check._current_time = mock.MagicMock(return_value=datetime.datetime.utcnow())
    instance.state = State({'last_processed_timestamp': check._current_time.return_value-datetime.timedelta(hours=15)})
    st, et = check.get_start_end_time_trace(instance)
    # state holds a time greater than MAX_TRACE_HISTORY_LIMIT, so start time will be reset and becomes now - 3 hrs
    assert st == check._current_time.return_value - datetime.timedelta(hours=MAX_TRACE_HISTORY_LIMIT)
    # since the state is reset, will process in batch of MAX_TRACE_HISTORY_BATCH_SIZE
    # end time = last time from state + MAX_TRACE_HISTORY_BATCH_SIZE
    assert et == st + datetime.timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)


@patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockBrokenAwsClient)
def test_service_check_broken_client(aggregator, instance):
    aws_check = AwsCheck('aws', {}, {}, instances=[instance])
    aws_check.run()
    # Service Checks should be generated
    service_checks = aggregator.service_checks(aws_check.SERVICE_CHECK_CONNECT_NAME)
    print("service checks are:- {}".format(service_checks))
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_CONNECT_NAME, aws_check.CRITICAL)
    assert 1 == 0


# @patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockAwsClient)
# @patch('stackstate_checks.aws_xray.aws_xray.requests.put', mock.MagicMock(return_value={'status_code': 202}))
# def test_service_check_ok(aggregator, instance):
#     instance = Instance(instance)
#     aws_check = AwsCheck('test', {}, {}, instances=[instance])
#     aws_check.fetch_batch_traces = mock.MagicMock(return_value=get_xray_traces())
#     # test instance key before check run
#     assert aws_check.get_instance_key(instance) == TopologyInstance('aws', 'arn:aws:iam::0123456789:role/OtherRoleName')
#     aws_check.run()
#     print(aggregator.service_check_names)
#     # test instance key after check run, assert that the account has been set
#     # assert aws_check.get_instance_key(instance) == TopologyInstance('aws', AWS_ACCOUNT)
#     aggregator.assert_service_check('aws_xray.can_connect', aws_check.OK)
#     aggregator.assert_service_check('aws_xray.can_execute', aws_check.OK)
#
#
# def test_no_role_arn(aggregator, instance_no_role_arn):
#     aws_check = AwsCheck('test', {}, {}, instances=[instance_no_role_arn])
#     assert aws_check.get_instance_key(instance_no_role_arn) == TopologyInstance('aws', 'unknown-instance')
#     aws_client = AwsClient(instance_no_role_arn, config={})
#     assert aws_client.aws_access_key_id == instance_no_role_arn.get('aws_access_key_id')
#     assert aws_client.aws_secret_access_key == instance_no_role_arn.get('aws_secret_access_key')
#     assert aws_client.aws_session_token is None
#
#
# def test_span_generation():
#     check = AwsCheck('test', {}, {})
#     segment = get_file('segment.json')
#     spans = check._generate_spans([segment])
#     assert len(spans) == 9
#
#
# def test_error_trace():
#     check = AwsCheck('test', {}, {})
#     segments = get_file('segments_error.json')
#     spans = check._generate_spans(segments)
#     assert len(spans) == 5
#     # 2 main segments should kind as client
#     assert spans[0]["meta"]["span.kind"] == "client"
#     assert spans[1]["meta"]["span.kind"] == "client"
#     # 3 subsegments should have kind as internal
#     assert spans[2]["meta"]["span.kind"] == "internal"
#     assert spans[3]["meta"]["span.kind"] == "internal"
#     assert spans[4]["meta"]["span.kind"] == "internal"
#     # should produce errorClass 4xx caused by `error`
#     assert spans[0]["meta"]["span.errorClass"] == '4xx'
#     assert spans[0]["error"]
#     # should produce errorClass 5xx caused by `fault`
#     assert spans[1]["meta"]["span.errorClass"] == '5xx'
#     assert spans[1]["error"]
#     # should produce errorClass 4xx caused by `throttle`
#     assert spans[3]["meta"]["span.errorClass"] == '4xx'
#     assert spans[3]["error"]
#
#
# def test_end_time():
#     client = AwsClient({}, {})
#     time1 = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
#     client.last_end_time = time1
#     client.write_cache_file()
#     time2 = client._get_last_request_end_time()
#     assert time1 == time2
#
#
# def test_end_time_older_than_24h():
#     client = AwsClient({}, {})
#     client.last_end_time = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
#     client.write_cache_file()
#     assert client.default_start_time() > datetime.datetime.utcnow() - datetime.timedelta(hours=3)
#
#
def get_file(file_name):
    file_with_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', file_name)
    with open(file_with_path, 'r') as file:
        object_from_json_file = jsonpickle.decode(file.read())
    return object_from_json_file
