# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import os

import jsonpickle
from mock import patch

from stackstate_checks.aws import AwsCheck
from stackstate_checks.aws.aws import AwsClient

AWS_REGION = 'eu-west-1'
AWS_ACCOUNT = '672574731473'


class MockAwsClient():
    def __init__(self, instance):
        self.region = AWS_REGION

    @staticmethod
    def get_xray_traces():
        traces = get_file('get_xray_traces.json')
        return traces

    @staticmethod
    def get_account_id():
        return AWS_ACCOUNT


def test_traces():
    check = AwsCheck('test', {}, {})
    aws_client = MockAwsClient({})
    check.region = aws_client.region
    check.account_id = aws_client.get_account_id()
    traces = check._process_xray_traces(aws_client)

    assert len(traces) == 3
    assert len(traces[0]) == 25
    assert len(traces[1]) == 25
    assert len(traces[2]) == 5


@patch('stackstate_checks.aws.aws.AwsClient', MockAwsClient)
def test_service_check(aggregator, instance):
    aws_check = AwsCheck('test', {}, {})
    aws_check.check(instance)
    aggregator.assert_service_check('aws.can_connect', aws_check.CRITICAL)


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


def test_end_time():
    client = AwsClient({}, {})
    time1 = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
    client.last_end_time = time1
    client.write_cache_file()
    time2 = client._get_last_request_end_time()
    assert time1 == time2


def get_file(file_name):
    file_with_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', file_name)
    with open(file_with_path, 'r') as file:
        object_from_json_file = jsonpickle.decode(file.read())
    return object_from_json_file
