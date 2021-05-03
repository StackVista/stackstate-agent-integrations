import unittest
import os
import json
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


def mock_boto_calls(operation_name, kwarg=None):
    if operation_name == "AssumeRole":
        return {
            "Credentials": {
                "AccessKeyId": "KEY_ID",
                "SecretAccessKey": "ACCESS_KEY",
                "SessionToken": "TOKEN"
            }
        }
    elif operation_name == 'ListStateMachines':
        return resource('json/stepfunctions/list_state_machines.json')
    elif operation_name == 'DescribeStateMachine':
        return resource('json/stepfunctions/describe_state_machine.json')
    elif operation_name == 'ListActivities':
        return {}
    elif operation_name == 'LookupEvents':
        return {}
    raise ValueError("Unknown operation name", operation_name)


class TestStepFunctions(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        self.patcher = patch("botocore.client.BaseClient._make_api_call")
        self.mock_object = self.patcher.start()
        top.reset()
        aggregator.reset()
        init_config = InitConfig({
            "aws_access_key_id": "some_key",
            "aws_secret_access_key": "some_secret",
            "external_id": "disable_external_id_this_is_unsafe"
        })
        instance = {
            "role_arn": "arn:aws:iam::731070500579:role/RoleName",
            "regions": ["eu-west-1"],
        }
        instance.update({"apis_to_run": ["stepfunctions|aws.stepfunction"]})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        self.mock_object.side_effect = mock_boto_calls

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    def xtest_process_stepfunctions(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        # print(json.dumps(topology[0]["components"], indent=2))
        for component in topology[0]["components"]:
            print(component["id"] + " - " + component["type"])
        for relation in topology[0]["relations"]:
            print('src: ' + relation["source_id"])
            print('dst: ' + relation["target_id"])
            print('tp : ' + relation["type"])
            print()
        self.assertEqual(len(topology[0]["components"]), 1)
