# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import os
import jsonpickle
from mock import patch

from stackstate_checks.aws_xray import AwsCheck
from stackstate_checks.aws_xray.aws_xray import AwsClient
from stackstate_checks.base import TopologyInstance

AWS_REGION = 'eu-west-1'
AWS_ACCOUNT = '672574731473'


class MockAwsClient:
    def __init__(self, instance, init_config):
        self.region = AWS_REGION

    @staticmethod
    def get_xray_traces():
        traces = get_file('get_xray_traces.json')
        return traces

    @staticmethod
    def get_account_id():
        return AWS_ACCOUNT

    @staticmethod
    def write_cache_file():
        pass


class MockBrokenAwsClient(MockAwsClient):

    @staticmethod
    def get_account_id():
        raise Exception("some dummy error: could not get the account id")


def test_traces():
    check = AwsCheck('test', {}, {})
    aws_client = MockAwsClient({}, {})
    check.region = aws_client.region
    check.account_id = aws_client.get_account_id()
    traces = check._process_xray_traces(aws_client)

    assert len(traces) == 3
    assert len(traces[0]) == 25
    assert len(traces[1]) == 25
    assert len(traces[2]) == 5


@patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockBrokenAwsClient)
def test_service_check_broken_client(aggregator, instance):
    aws_check = AwsCheck('test', {}, {}, instances=[instance])
    aws_check.run()
    aggregator.assert_service_check('aws_xray.can_connect', aws_check.CRITICAL)


@patch('stackstate_checks.aws_xray.aws_xray.AwsClient', MockAwsClient)
def test_service_check_ok(aggregator, instance):
    aws_check = AwsCheck('test', {}, {}, instances=[instance])
    # TODO: fix these tests and don't do this. Doing this as an interim fix to skip the _send_payload function
    aws_check._send_payload = lambda traces: "{}"
    # test instance key before check run
    assert aws_check.get_instance_key(instance) == TopologyInstance('aws', 'arn:aws:iam::0123456789:role/OtherRoleName')
    result = aws_check.run()
    assert result == ''
    # test instance key after check run, assert that the account has been set
    assert aws_check.get_instance_key(instance) == TopologyInstance('aws', AWS_ACCOUNT)
    aggregator.assert_service_check('aws_xray.can_connect', aws_check.OK)
    aggregator.assert_service_check('aws_xray.can_execute', aws_check.OK)


def test_no_role_arn(aggregator, instance_no_role_arn):
    aws_check = AwsCheck('test', {}, {}, instances=[instance_no_role_arn])
    assert aws_check.get_instance_key(instance_no_role_arn) == TopologyInstance('aws', 'unknown-instance')
    aws_client = AwsClient(instance_no_role_arn, config={})
    assert aws_client.aws_access_key_id == instance_no_role_arn.get('aws_access_key_id')
    assert aws_client.aws_secret_access_key == instance_no_role_arn.get('aws_secret_access_key')
    assert aws_client.aws_session_token is None


def test_span_generation():
    check = AwsCheck('test', {}, {})
    segment = get_file('segment.json')
    spans = check._generate_spans([segment])
    assert len(spans) == 9


def test_error_trace():
    check = AwsCheck('test', {}, {})
    segments = get_file('segments_error.json')
    spans = check._generate_spans(segments)
    assert len(spans) == 5
    assert spans[0]['error'] == 1
    assert spans[1]['error'] == 1
    assert spans[0]["meta"]["span.kind"] == "client"


def test_end_time():
    client = AwsClient({}, {})
    time1 = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
    client.last_end_time = time1
    client.write_cache_file()
    time2 = client._get_last_request_end_time()
    assert time1 == time2


def test_end_time_older_than_24h():
    client = AwsClient({}, {})
    client.last_end_time = datetime.datetime.utcnow() - datetime.timedelta(hours=48)
    client.write_cache_file()
    assert client.default_start_time() > datetime.datetime.utcnow() - datetime.timedelta(hours=24)


def get_file(file_name):
    file_with_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', file_name)
    with open(file_with_path, 'r') as file:
        object_from_json_file = jsonpickle.decode(file.read())
    return object_from_json_file
