# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import unittest
from mock import patch

from stackstate_checks.aws_topology import AwsClient, InstanceInfo

REGION = "test-region"
KEY_ID = "1234"
ACCESS_KEY = "5678"
ACCOUNT_ID = "123456789012"
ROLE = "some_role_with_many_characters"
TOKEN = "ABCDE"

instance = InstanceInfo(
    {
        "aws_access_key_id": KEY_ID,
        "aws_secret_access_key": ACCESS_KEY,
        "role_arn": ROLE,
        "account_id": ACCOUNT_ID,
        "region": REGION
    }
)

instance_no_input = InstanceInfo({

})


class TestAWSClient(unittest.TestCase):
    """Basic Test for AWS Topology integration."""

    def test_no_token_gives_exception(self):
        def results(operation_name, kwarg):
            api_results = {
                'AssumeRole': {
                    "Credentials": {
                        "AccessKeyId": KEY_ID,
                        "SecretAccessKey": ACCESS_KEY,
                        "SessionToken": None
                    }
                }
            }
            return api_results[operation_name]
        with patch('botocore.client.BaseClient._make_api_call') as mock_method:
            mock_method.side_effect = results
            with self.assertRaises(Exception) as context:
                AwsClient(instance, {})
        self.assertIn('no session token', str(context.exception))

    def test_no_input_gives_exception(self):
        with self.assertRaises(Exception) as context:
            AwsClient(instance_no_input, {})
        self.assertIn('no session token', str(context.exception))

    def test_client_connect(self):
        api_results = {
            'AssumeRole': {
                "Credentials": {
                    "AccessKeyId": KEY_ID,
                    "SecretAccessKey": ACCESS_KEY,
                    "SessionToken": TOKEN
                }
            }
        }

        def results(operation_name, kwarg):
            return api_results[operation_name]
        with patch('botocore.client.BaseClient._make_api_call') as mock_method:
            mock_method.side_effect = results
            client = AwsClient(instance, {})
        self.assertEqual(client.region, REGION)
        self.assertEqual(client.aws_access_key_id, KEY_ID)
        self.assertEqual(client.aws_secret_access_key, ACCESS_KEY)
        self.assertEqual(client.aws_session_token, TOKEN)
        assert mock_method.called_once_with('AssumeRole', {'RoleArn': ROLE, 'RoleSessionName': 'sts-agent-check'})

    def test_get_account_id(self):
        api_results = {
            'AssumeRole': {
                "Credentials": {
                    "AccessKeyId": KEY_ID,
                    "SecretAccessKey": ACCESS_KEY,
                    "SessionToken": TOKEN
                }
            },
            'GetCallerIdentity': {
                "Account": ACCOUNT_ID,
            }
        }

        def results(operation_name, kwarg):
            return api_results[operation_name]
        with patch('botocore.client.BaseClient._make_api_call') as mock_method:
            mock_method.side_effect = results
            client = AwsClient(instance, {})
            id = client.get_account_id()
        self.assertEqual(id, ACCOUNT_ID)
