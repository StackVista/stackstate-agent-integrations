# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from datetime import timedelta, datetime
import os

import jsonpickle
import mock
from mock import patch

from stackstate_checks.aws_xray import AwsCheck
from stackstate_checks.aws_xray.aws_xray import MAX_TRACE_HISTORY_LIMIT, MAX_TRACE_HISTORY_BATCH_SIZE, \
    Instance, State


AWS_REGION = 'eu-west-1'
AWS_ACCOUNT = '672574731473'


def get_xray_traces():
    traces = get_file('get_xray_traces.json')
    return traces


def string_to_datetime(time):
    return datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%f")


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


@patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockAwsClient)
@patch('requests.put', mock.MagicMock(status_code=202, text="ok"))
def test_check_run_normal_start(aws_check, aggregator):
    """
    Test to check if we process in the proper batch size
    state should be (utc - MAX_TRACE_HISTORY_LIMIT hrs) + MAX_TRACE_HISTORY_BATCH_SIZE
    """
    aws_check.fetch_batch_traces = mock.MagicMock(return_value=get_xray_traces())
    aws_check._current_time = mock.MagicMock(return_value=datetime.utcnow())
    aws_check.run()
    # by default the start time is utc - trace history limit + 1 min
    starting_state_time = aws_check._current_time.return_value - timedelta(hours=MAX_TRACE_HISTORY_LIMIT) + timedelta(
        minutes=1)
    # end time should be start time + default batch size
    end_time = starting_state_time + timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)
    # get state from the state manager
    state_descriptor = aws_check._get_state_descriptor()
    state = aws_check.state_manager.get_state(state_descriptor)
    # state should be equal to end time
    assert datetime.strptime(state.get('last_processed_timestamp'), "%Y-%m-%dT%H:%M:%S.%f") == end_time

    # Ok Service Check should be generated for Execute and Connect
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_EXECUTE_NAME, aws_check.OK)
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_CONNECT_NAME, aws_check.OK)


@patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockAwsClient)
@patch('requests.put', mock.MagicMock(status_code=202, text="ok"))
def test_check_run_already_lagging_behind(aws_check, aggregator):
    """
    Test to check if we fetch from state process in the proper batch size if lagging behind
    less than MAX_TRACE_HISTORY_LIMIT
    At the end state should be starting state + MAX_TRACE_HISTORY_BATCH_SIZE
    """
    aws_check._current_time = mock.MagicMock(return_value=datetime(2021, 7, 12, 18, 27, 17, 10822))
    aws_check.fetch_batch_traces = mock.MagicMock(return_value=get_xray_traces())

    # set the state in the check before it starts
    state = State({'last_processed_timestamp': "2021-07-12T16:27:17.293178"})
    state_descriptor = aws_check._get_state_descriptor()
    aws_check.state_manager.set_state(state_descriptor, state)

    aws_check.run()
    # since we are lagging around 2 hrs behind, we process in batch of MAX_TRACE_HISTORY_BATCH_SIZE
    end_time = state.last_processed_timestamp + timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)

    # get state from the state manager
    state = aws_check.state_manager.get_state(state_descriptor)

    # state should be equal to end time
    assert string_to_datetime(state.get('last_processed_timestamp')) == end_time

    # Ok Service Check should be generated for Execute and Connect
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_EXECUTE_NAME, aws_check.OK)
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_CONNECT_NAME, aws_check.OK)


@patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockAwsClient)
@patch('requests.put', mock.MagicMock(status_code=202, text="ok"))
def test_check_run_lagging_behind_more_than_10hrs(aws_check, aggregator):
    """
    Test to check if we reset the state and fetch from utc - 3 in the proper batch size if lagging behind
    more than MAX_TRACE_HISTORY_LIMIT
    At the end state should be (utc - 3) + MAX_TRACE_HISTORY_BATCH_SIZE
    """
    aws_check._current_time = mock.MagicMock(return_value=datetime.utcnow())
    aws_check.fetch_batch_traces = mock.MagicMock(return_value=get_xray_traces())

    # since state stores the time as string
    # set the state in the check before it starts
    state = State({'last_processed_timestamp': "2021-07-12T10:27:17.293178"})
    state_descriptor = aws_check._get_state_descriptor()
    aws_check.state_manager.set_state(state_descriptor, state)

    aws_check.run()
    # since we are lagging more than MAX_TRACE_HISTORY_LIMIT, reset the state with utc -3
    start_time = aws_check._current_time.return_value - timedelta(hours=MAX_TRACE_HISTORY_LIMIT)
    # end time should be start time + batch size
    end_time = start_time + timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)
    # get the state from check state manager
    state = aws_check.state_manager.get_state(state_descriptor)

    # state should be equal to end time
    assert string_to_datetime(state.get('last_processed_timestamp')) == end_time

    # Ok Service Check should be generated for Execute and Connect
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_EXECUTE_NAME, aws_check.OK)
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_CONNECT_NAME, aws_check.OK)


@patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockAwsClient)
def test_check_run_exception_no_state_persistence(aws_check, aggregator):
    """
    Test to check there should be no state persisted in the check if exception is thrown
    """
    aws_check.fetch_batch_traces = mock.MagicMock(side_effect=Exception("API Error"))
    aws_check._current_time = mock.MagicMock(return_value=datetime.utcnow())
    aws_check.run()
    # get state from the state manager
    state_descriptor = aws_check._get_state_descriptor()
    state = aws_check.state_manager.get_state(state_descriptor)
    # state should not be written if exception is thrown
    assert state is None

    # Ok Service Check should be generated for Execute and Connect
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_EXECUTE_NAME, aws_check.CRITICAL)


def test_get_start_end_time_trace_normal_start(instance):
    """
    Test get_start_end_time_trace for the normal start scenario
    """
    # get the instance schema object for instance
    instance = Instance(instance)

    aws_check = AwsCheck('aws', {}, {}, [instance])
    aws_check._current_time = mock.MagicMock(return_value=datetime.utcnow())
    # since there is no state, default start time will be now - 3 hrs + 1 min
    last_trace_end_timestamp = aws_check._current_time.return_value - timedelta(
        hours=MAX_TRACE_HISTORY_LIMIT) + timedelta(minutes=1)

    st, et = aws_check.get_start_end_time_trace(instance)
    # since there is no state, default start time will be now - 3 hrs + 1 min
    assert st == last_trace_end_timestamp
    # since diff is 3 hrs, we will process in batch with end time = start + MAX_TRACE_HISTORY_BATCH_SIZE
    assert et == last_trace_end_timestamp + timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)


def test_get_start_end_time_trace_lagging_15_mins(instance):
    """
    Test get_start_end_time_trace when state is behind less than trace history limit
    but more than default trace batch size
    """
    # get the instance schema object for instance
    instance = Instance(instance)

    aws_check = AwsCheck('aws', {}, {}, [instance])
    aws_check._current_time = mock.MagicMock(return_value=datetime.utcnow())
    # set the state in instance before calling the method
    instance.state = State({'last_processed_timestamp': aws_check._current_time.return_value-timedelta(minutes=15)})

    last_trace_end_timestamp = instance.state.last_processed_timestamp + timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)
    st, et = aws_check.get_start_end_time_trace(instance)
    # state holds a time 15 minutes behind, so start time will be from state
    assert st == instance.state.last_processed_timestamp
    # since the time from state is still lagging behind more than MAX_TRACE_HISTORY_BATCH_SIZE but less than
    # MAX_TRACE_HISTORY_LIMIT, so end time should be last time from state + MAX_TRACE_HISTORY_BATCH_SIZE
    assert et == last_trace_end_timestamp


def test_get_start_end_time_trace_lagging_15_hrs(instance):
    """
    Test get_start_end_time_trace when state is behind more than trace history limit
    """
    # get the instance schema object for instance
    instance = Instance(instance)

    aws_check = AwsCheck('aws', {}, {}, [instance])
    aws_check._current_time = mock.MagicMock(return_value=datetime.utcnow())
    # set the state in instance before calling the method
    instance.state = State({'last_processed_timestamp': aws_check._current_time.return_value-timedelta(hours=15)})
    st, et = aws_check.get_start_end_time_trace(instance)
    # state holds a time greater than MAX_TRACE_HISTORY_LIMIT, so start time will be reset and becomes now - 3 hrs
    assert st == aws_check._current_time.return_value - timedelta(hours=MAX_TRACE_HISTORY_LIMIT)
    # since the state is reset, will process in batch of MAX_TRACE_HISTORY_BATCH_SIZE
    # end time should be last time from state + MAX_TRACE_HISTORY_BATCH_SIZE
    assert et == st + timedelta(minutes=MAX_TRACE_HISTORY_BATCH_SIZE)


@patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockBrokenAwsClient)
def test_service_check_broken_client(aggregator, instance):
    """
    Test to check if critical service check is produced in case of AWSClient throws exception
    """
    aws_check = AwsCheck('aws', {}, {}, instances=[instance])
    aws_check.run()
    # critical service check should be generated for AWSClient
    aggregator.assert_service_check(aws_check.SERVICE_CHECK_CONNECT_NAME, aws_check.CRITICAL)


def test_span_generation():
    """
    Test to check the number of spans generated
    """
    check = AwsCheck('test', {}, {})
    segment = get_file('segment.json')
    spans = check._generate_spans([segment])
    assert len(spans) == 9


def test_error_trace():
    """
    Test to check if correct errorClass and kind is produced in the generated spans
    """
    check = AwsCheck('test', {}, {})
    segments = get_file('segments_error.json')
    spans = check._generate_spans(segments)
    assert len(spans) == 5
    # 2 main segments should kind as client
    assert spans[0]["meta"]["span.kind"] == "client"
    assert spans[1]["meta"]["span.kind"] == "client"
    # 3 subsegments should have kind as internal
    assert spans[2]["meta"]["span.kind"] == "internal"
    assert spans[3]["meta"]["span.kind"] == "internal"
    assert spans[4]["meta"]["span.kind"] == "internal"
    # should produce errorClass 4xx caused by `error`
    assert spans[0]["meta"]["span.errorClass"] == '4xx'
    assert spans[0]["error"]
    # should produce errorClass 5xx caused by `fault`
    assert spans[1]["meta"]["span.errorClass"] == '5xx'
    assert spans[1]["error"]
    # should produce errorClass 4xx caused by `throttle`
    assert spans[3]["meta"]["span.errorClass"] == '4xx'
    assert spans[3]["error"]


def get_file(file_name):
    """
    Return content from the file name
    """
    file_with_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', file_name)
    with open(file_with_path, 'r') as file:
        object_from_json_file = jsonpickle.decode(file.read())
    return object_from_json_file
