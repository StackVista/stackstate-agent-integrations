# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import unittest
from mock import patch
from copy import deepcopy

from stackstate_checks.base.stubs import topology, aggregator
from stackstate_checks.base import AgentCheck
from stackstate_checks.aws_topology import AwsTopologyCheck

from .test_aws_topology import API_RESULTS

BUCKET_NAME = "testname"
SIMPLE_BUCKET = {
    'ListBuckets': {
        'Buckets': [{
            'Name': BUCKET_NAME
        }]
    }
}
LAMBDA_ARN = "arn:aws:lambda:eu-west-1:731070500579:function:" + \
    "com-stackstate-prod-s-NotifyBucketEventsHandle-1W0B5NSZYJ3G1"

# TODO also test extra data


@pytest.mark.usefixtures("instance")
class TestS3(unittest.TestCase):
    """Basic Test for AWS Topology integration."""

    CHECK_NAME = 'aws_topology'
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        config = {}
        self.patcher = patch('botocore.client.BaseClient._make_api_call')
        self.mock_object = self.patcher.start()
        self.api_results = deepcopy(API_RESULTS)
        topology.reset()
        aggregator.reset()
        self.check = AwsTopologyCheck(self.CHECK_NAME, config, instances=[self.instance])

        def results(operation_name, kwarg):
            return self.api_results.get(operation_name) or {}

        self.mock_object.side_effect = results

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK)

    def test_simple_bucket(self):
        self.api_results.update(SIMPLE_BUCKET)
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['components']), 1)
        self.assertEqual(test_topology['components'][0]['type'], 'aws.s3_bucket')
        self.assertEqual(test_topology['components'][0]['id'], 'arn:aws:s3:::testname')
        self.assert_executed_ok()

    def test_bucket_with_location(self):
        self.api_results.update(SIMPLE_BUCKET)
        self.api_results.update({
            'GetBucketLocation': {
                "LocationConstraint": "eu-west-1"
            }
        })
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['components']), 1)
        self.assertIsNotNone(test_topology['components'][0]['data'])
        self.assertEqual(test_topology['components'][0]['data']['BucketLocation'], 'eu-west-1')
        self.assert_executed_ok()

    def test_bucket_with_tags(self):
        self.api_results.update(SIMPLE_BUCKET)
        self.api_results.update({
            'GetBucketTagging': {
                "TagSet": [
                    {
                        "Key": "tagkey",
                        "Value": "tagvalue"
                    }
                ]
            }
        })
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['components']), 1)
        self.assertIsNotNone(test_topology['components'][0]['data'])
        self.assertEqual(test_topology['components'][0]['data']['Tags'], {'tagkey': 'tagvalue'})
        self.assert_executed_ok()

    def test_bucket_with_notifications(self):
        self.api_results.update(SIMPLE_BUCKET)
        EVENT1 = "s3:ObjectRemoved:*"
        EVENT2 = "s3:ObjectCreated:*"
        self.api_results.update({
            'GetBucketNotificationConfiguration': {
                "LambdaFunctionConfigurations": [
                    {
                        "Id": "4650b182-c9c3-4c3f-8d2f-a2d78a8b9ad4",
                        "LambdaFunctionArn": LAMBDA_ARN,
                        "Events": [
                            EVENT1
                        ]
                    },
                    {
                        "Id": "2bd6fed8-6a74-47c7-96e5-d0a02c136997",
                        "LambdaFunctionArn": LAMBDA_ARN,
                        "Events": [
                            EVENT2
                        ]
                    }
                ]
            }
        })
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['relations']), 2)
        self.assertEqual(
            test_topology['relations'][0],
            {
                'source_id': 'arn:aws:s3:::testname',
                'target_id': LAMBDA_ARN,
                'type': 'uses service',
                'data': {'event_type': EVENT1}
            }
        )
        self.assertEqual(
            test_topology['relations'][1],
            {
                'source_id': 'arn:aws:s3:::testname',
                'target_id': LAMBDA_ARN,
                'type': 'uses service',
                'data': {'event_type': EVENT2}
            }
        )
        self.assert_executed_ok()
