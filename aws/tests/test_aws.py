# (C) Datadog, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

import jsonpickle

from stackstate_checks.aws import AwsCheck

AWS_REGION = 'eu-west-1'
AWS_ACCOUNT = '672574731473'

class MockAwsClient():
    def __init__(self, instance):
        self.region = AWS_REGION

    @staticmethod
    def get_xray_traces():
        file_name = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'get_xray_traces.json')
        with open(file_name) as file:
            trace = file.read()
            return jsonpickle.decode(trace)

    @staticmethod
    def get_account_id():
        return AWS_ACCOUNT


def test_traces(aggregator, instance):
    check = AwsCheck('aws', {}, {})
    aws_client = MockAwsClient({})
    check.region = aws_client.region
    check.account_id = aws_client.get_account_id()
    traces = check._process_xray_traces(aws_client)

    assert len(traces) == 2
    assert len(traces[0]) == 25
    assert len(traces[1]) == 25

    aggregator.assert_all_metrics_covered()
