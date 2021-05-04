# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import unittest
from mock import patch
import botocore

from stackstate_checks.aws_topology import AwsClient, InstanceInfo, InitConfig

REGIONS = ["test-region"]
KEY_ID = "1234"
ACCESS_KEY = "5678"
ACCOUNT_ID = "123456789012"
ROLE = "arn:aws:iam::123456789012:role/RoleName"
TOKEN = "ABCDE"
EXTERNAL_ID = "ABCDE"

init_config = InitConfig(
    {
        "aws_access_key_id": KEY_ID,
        "aws_secret_access_key": ACCESS_KEY,
        "external_id": EXTERNAL_ID
    }
)

instance = InstanceInfo(
    {
        "role_arn": ROLE,
        "regions": REGIONS,
    }
)

instance_no_input = InstanceInfo({

})


class TestAWSClient(unittest.TestCase):
    """Basic Test for AWS Topology integration."""

    # def test_no_token_gives_exception(self):
    #     def results(operation_name, kwarg):
    #         api_results = {
    #             'AssumeRole': {
    #                 "Credentials": {
    #                     "AccessKeyId": KEY_ID,
    #                     "SecretAccessKey": ACCESS_KEY,
    #                     "SessionToken": None
    #                 }
    #             }
    #         }
    #         return api_results[operation_name]
    #     with patch('botocore.client.BaseClient._make_api_call') as mock_method:
    #         mock_method.side_effect = results
    #         with self.assertRaises(Exception) as context:
    #             AwsClient(init_config)
    #     self.assertIn('no session token', str(context.exception))

    def test_no_external_id_gives_exception(self):
        def results(operation_name, api_params):
            if operation_name == 'AssumeRole' and 'external_id' in api_params:
                return {
                    "Credentials": {
                        "AccessKeyId": KEY_ID,
                        "SecretAccessKey": ACCESS_KEY,
                        "SessionToken": TOKEN
                    }
                }
            else:
                raise botocore.exceptions.ClientError({
                    'Error': {
                        'Code': 'AccessDenied'
                    }
                }, operation_name)
        with patch('botocore.client.BaseClient._make_api_call') as mock_method:
            mock_method.side_effect = results
            with self.assertRaises(Exception) as context:
                client = AwsClient(InitConfig(
                    {
                        "aws_access_key_id": KEY_ID,
                        "aws_secret_access_key": ACCESS_KEY
                    }
                ))
                client.get_session(instance['regions'][0], instance['role_arn'])
        self.assertIn('AccessDenied', str(context.exception))

    def test_no_input_gives_exception(self):
        with self.assertRaises(Exception) as context:
            AwsClient(instance_no_input)
        self.assertIn('external_id', str(context.exception))

    def test_client_connect(self):
        def results(operation_name, api_params):
            if operation_name == 'AssumeRole' and 'ExternalId' in api_params:
                return {
                    "Credentials": {
                        "AccessKeyId": KEY_ID,
                        "SecretAccessKey": ACCESS_KEY,
                        "SessionToken": TOKEN
                    }
                }
            else:
                raise botocore.exceptions.ClientError({
                    'Error': {
                        'Code': 'AccessDenied'
                    }
                }, operation_name)
        with patch('botocore.client.BaseClient._make_api_call') as mock_method:
            mock_method.side_effect = results
            client = AwsClient(init_config)
            session = client.get_session(instance['role_arn'], instance['regions'][0])
        self.assertEqual(session.region_name, REGIONS[0])
        self.assertEqual(session.get_credentials().access_key, KEY_ID)
        self.assertEqual(session.get_credentials().secret_key, ACCESS_KEY)
        self.assertEqual(session.get_credentials().token, TOKEN)
        assert mock_method.called_once_with('AssumeRole', {
            'RoleArn': ROLE,
            'RoleSessionName': 'sts-agent-check',
            'ExternalId': EXTERNAL_ID
        })
