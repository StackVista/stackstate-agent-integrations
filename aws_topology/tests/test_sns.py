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

from .conftest import API_RESULTS

TOPIC_ARN = "arn:aws:sns:eu-west-1:731070500579:my-topic-1"
SIMPLE_SNS = {
    'ListTopics': {
        "Topics": [
            {
                "TopicArn": TOPIC_ARN
            }
        ]
    }
}

# TODO also test extra data


@pytest.mark.usefixtures("instance")
class TestSns(unittest.TestCase):
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
        self.api_results.update(SIMPLE_SNS)
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['components']), 1)
        self.assertEqual(test_topology['components'][0]['type'], 'aws.sns')
        self.assertEqual(test_topology['components'][0]['id'], TOPIC_ARN)
        self.assertEqual(test_topology['components'][0]['data']['Name'], TOPIC_ARN)
        self.assert_executed_ok()

    def test_bucket_with_tags(self):
        self.api_results.update(SIMPLE_SNS)
        self.api_results.update({
            'ListTagsForResource': {
                "Tags": [
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
