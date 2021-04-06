# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import unittest
from mock import patch
from copy import deepcopy

from stackstate_checks.base.stubs import topology, aggregator
from stackstate_checks.base import AgentCheck
from stackstate_checks.aws_topology import AwsTopologyCheck, InstanceInfo, memory_data

REGION = "test-region"
KEY_ID = "1234"
ACCESS_KEY = "5678"
ACCOUNT_ID = "123456789012"
WRONG_ACCOUNT_ID = "987654321012"
ROLE = "some_role_with_many_characters"
TOKEN = "ABCDE"

API_RESULTS = {
    'AssumeRole': {
        "Credentials": {
            "AccessKeyId": KEY_ID,
            "SecretAccessKey": ACCESS_KEY,
            "SessionToken": TOKEN
        }
    },
    'GetCallerIdentity': {
        "Account": ACCOUNT_ID,
    },
}


@pytest.mark.usefixtures("instance")
class TestAWSTopologyCheck(unittest.TestCase):
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

    def test_collect_empty_topology(self):
        """
        Testing AWS Topology check should not produce any topology (apis_to_run set to empty array)
        """
        config = InstanceInfo(
            {
                "aws_access_key_id": "some_key",
                "aws_secret_access_key": "some_secret",
                "role_arn": "some_role",
                "account_id": "123456789012",
                "region": "eu-west-1",
                "apis_to_run": []
            }
        )

        self.check.check(config)
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(test_topology['instance_key'], {'type': 'aws', 'url': '123456789012'})
        self.assertEqual(test_topology['components'], [])
        self.assertEqual(test_topology['relations'], [])
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_CONNECT_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK)
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK)

    def test_connect_failure(self):
        """
        Testing connection failure
        """
        self.api_results['GetCallerIdentity']['Account'] = WRONG_ACCOUNT_ID
        self.check.run()

        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_CONNECT_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertIn('caller identity does not return correct account_id', service_checks[0].message)

    def test_execute_failure(self):
        """
        Testing execution failure
        """
        def raise_error():
            raise Exception("error")
        self.check.APIS = {
            's3': {'memory_key': 'test_key', 'parts': [lambda i, c, a: raise_error()]}
        }
        self.check.run()
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertIn('topology collection failed', service_checks[0].message)

    def test_topology_memory(self):
        """
        Testing memory
        """
        self.check.APIS = {
            's3': {'memory_key': 'test_key', 'parts': [lambda i, c, a: {'abc': 'def'}]},
            'autoscaling': {'parts': [lambda i, c, a: None]},
            'ec2': {'parts': [lambda i, c, a: {'xyz': 'xyz'}, lambda i, a, c: {'ttt': 'ttt'}]}
        }
        self.check.run()
        self.assertEqual(memory_data.get('test_key'), {'abc': 'def'})
        self.assertEqual(memory_data.get('autoscaling'), None)
        self.assertEqual(memory_data.get('ec2'), {'xyz': 'xyz', 'ttt': 'ttt'})

    def test_metadata(self):
        self.api_results.update({
            'ListBuckets': {
                'Buckets': [{
                    'Name': 'testname'
                }]
            }
        })
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        print(test_topology)
        self.assertEqual(len(test_topology['components']), 1)
        self.assertIsNotNone(test_topology['components'][0]['data'])
        self.assertEqual(test_topology['components'][0]['data']['Tags'], {})
        self.assertEqual(
            test_topology['components'][0]['data']['Location'],
            {'AwsAccount': '123456789012', 'AwsRegion': 'eu-west-1'}
        )
        self.assertEqual(
            test_topology['components'][0]['data']['tags'],
            ['integration-type:aws', 'integration-url:123456789012']
        )
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEquals(service_checks[0].status, AgentCheck.OK)
