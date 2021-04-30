# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import unittest
from mock import patch
from copy import deepcopy
from botocore.exceptions import ClientError
from stackstate_checks.base.stubs import topology, aggregator
from stackstate_checks.base import AgentCheck
from stackstate_checks.aws_topology import AwsTopologyCheck, InstanceInfo, InitConfig

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
        config = InitConfig(
            {
                "aws_access_key_id": "some_key",
                "aws_secret_access_key": "some_secret",
                "external_id": "secret_string"
            }
        )
        self.patcher = patch('botocore.client.BaseClient._make_api_call')
        self.mock_object = self.patcher.start()
        self.api_results = deepcopy(API_RESULTS)
        topology.reset()
        aggregator.reset()
        self.check = AwsTopologyCheck(self.CHECK_NAME, config, [self.instance])

        def results(operation_name, api_params):
            if operation_name == 'AssumeRole' and 'ExternalId' not in api_params:
                raise ClientError({
                    'Error': {
                        'Code': 'AccessDeniedException'
                    }
                }, operation_name)
            else:
                return self.api_results.get(operation_name) or {}

        self.mock_object.side_effect = results

    def test_collect_empty_topology(self):
        """
        Testing AWS Topology check should not produce any topology (apis_to_run set to empty array)
        """
        instance = InstanceInfo(
            {
                "role_arn": "arn:aws:iam::123456789012:role/RoleName",
                "regions": ["eu-west-1"],
                "apis_to_run": []
            }
        )
        self.check.check(instance)
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

    # def test_connect_failure(self):
    #     """
    #     Testing connection failure
    #     """
    #     self.api_results['GetCallerIdentity']['Account'] = WRONG_ACCOUNT_ID
    #     self.check.run()

    #     service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_CONNECT_NAME)
    #     self.assertGreater(len(service_checks), 0)
    #     self.assertIn('caller identity does not return correct account_id', service_checks[0].message)

    def test_execute_failure(self):
        """
        Testing execution failure
        """

        class s3(object):
            API = "s3"

            def __init__(self, location_info, client, agent):
                pass

            def process_all(self):
                raise Exception("error")

        registry = {
            'regional': {
                's3': {
                    'aws.s3': s3
                }
            },
            'global': {}
        }

        self.check.APIS = {
            'regional': {
                's3': {}
            }
        }
        with patch('stackstate_checks.aws_topology.resources.ResourceRegistry.get_registry', return_value=registry):
            self.check.run()
            service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
            self.assertGreater(len(service_checks), 0)
            self.assertIn('topology collection failed', service_checks[0].message)

    def test_topology_memory(self):
        """
        Testing memory
        """
        class base(object):
            API = "??"
            API_TYPE = "??"
            MEMORY_KEY = None

            def __init__(self, location_info, client, agent):
                pass

            def get_delete_ids(self):
                return []

        class s3(base):
            API = "s3"
            API_TYPE = "regional"
            MEMORY_KEY = 'test_key'

            def process_all(self):
                return {'abc': 'def'}

        class ec2_1(base):
            API = "ec2"
            API_TYPE = "regional"
            COMPONENT_TYPE = "ec2_1"

            def process_all(self):
                return {'xyz': 'xyz'}

        class ec2_2(base):
            API = "ec2"
            API_TYPE = "regional"
            COMPONENT_TYPE = "ec2_2"

            def process_all(self):
                return {'ttt': 'ttt'}

        class autoscaling(base):
            API = "autoscaling"
            API_TYPE = "regional"

            def process_all(self):
                pass

        registry = {
            'regional': {
                's3': {
                    'aws.s3': s3
                },
                'ec2': {
                    'aws.1': ec2_1,
                    'aws.2': ec2_2
                },
                'autoscaling': {
                    'autoscaling': autoscaling
                }
            },
            'global': {}
        }
        with patch('stackstate_checks.aws_topology.resources.ResourceRegistry.get_registry', return_value=registry):
            self.check.run()
            self.assertEqual(self.check.memory_data.get('test_key'), {'abc': 'def'})
            self.assertEqual(self.check.memory_data.get('autoscaling'), None)
            self.assertEqual(self.check.memory_data.get('ec2'), {'xyz': 'xyz', 'ttt': 'ttt'})

    def test_metadata(self):
        self.api_results.update({
            'ListBuckets': {
                'Buckets': [{
                    'Name': 'testname'
                }]
            }
        })
        self.check.run()
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertEquals(service_checks[0].status, AgentCheck.OK)
        test_topology = topology.get_snapshot(self.check.check_id)
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
        self.assertGreater(len(service_checks), 0)
