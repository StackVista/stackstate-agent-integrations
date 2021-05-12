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


gaadcnt = 0


def mock_boto_calls(operation_name, kwarg=None):
    global gaadcnt
    if operation_name == "AssumeRole":
        return {
            "Credentials": {
                "AccessKeyId": "KEY_ID",
                "SecretAccessKey": "ACCESS_KEY",
                "SessionToken": "TOKEN"
            }
        }
    elif operation_name == 'GetAccountAuthorizationDetails':
        gaadcnt += 1
        return resource('json/iam/data' + str(gaadcnt) + '.json')
    elif operation_name == 'LookupEvents':
        return {}
    raise ValueError("Unknown operation name", operation_name)


class TestIAM(unittest.TestCase):

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
            "role_arn": "arn:aws:iam::548105126730:role/RoleName",
            "regions": ["global"],
        }
        instance.update({"apis_to_run": ["iam"]})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        self.mock_object.side_effect = mock_boto_calls

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    def assert_has_component(self, components, id, type):
        for component in components:
            if component["id"] == id and component["type"] == type:
                return component
        self.assertTrue(False, "Component expected id={} type={}".format(id, type))

    def assert_has_relation(self, relations, source_id, target_id):
        for relation in relations:
            if relation["source_id"] == source_id and relation["target_id"] == target_id:
                return relation
        self.assertTrue(False, "Relation expected source_id={} target_id={}".format(source_id, target_id))

    def test_process_iam(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        prefix = 'arn:aws:iam::548105126730:'
        stackname = 'stackstate-main-account-main-region'
        stackname_main = 'stackstate-main-account-main'

        def get_arn(type, resource_id):
            return prefix + type + '/' + stackname + '-' + resource_id

        def get_main_arn(type, resource_id):
            return prefix + type + '/' + stackname_main + '-' + resource_id

        user_name = get_arn('user', 'IamUser-15TGMT5HZF5DI')
        group_name = get_arn('group', 'IamGroup-4VHDGMM9UW6T')
        user_inline_policy_name = user_name + ':inlinepolicy/default'
        group_inline_policy_name = group_name + ':inlinepolicy/default'
        attached_policy_name = get_arn('policy', 'IamPolicy1-1AW49Q1P522SI')
        user_boundary_policy = get_arn('policy', 'IamPolicy2-1RRB2VKZ2W6XT')
        self.assert_has_component(components, user_name, 'aws.iam.user')
        self.assert_has_relation(relations, user_name, group_name)
        self.assert_has_relation(relations, user_name, user_inline_policy_name)
        self.assert_has_relation(relations, user_name, attached_policy_name)
        self.assert_has_relation(relations, group_name, group_inline_policy_name)
        self.assert_has_relation(relations, group_name, attached_policy_name)
        self.assert_has_relation(relations, user_name, user_boundary_policy)

        role_name = get_main_arn('role', 'LambdaFunctionIamRole-YGZTZWG466RL')
        role_attached_policy_name = get_arn('policy', 'LambdaFunctionIamPolicy1-S830ZCGAC77D')
        role_inline_policy_name = role_name + ':inlinepolicy/lambda'
        self.assert_has_component(components, role_name, 'aws.iam.role')
        self.assert_has_component(components, role_attached_policy_name, 'aws.iam.policy')
        self.assert_has_relation(relations, role_name, role_attached_policy_name)
        self.assert_has_relation(relations, role_name, role_inline_policy_name)
        self.assert_has_relation(relations, role_name, 'arn:aws:iam::aws:policy/AdministratorAccess')

        instance_profile_name = get_arn('instance-profile', 'EcsEc2InstanceProfile-12GND3YV6SNCD')
        role_name = get_arn('role', 'EcsEc2IamRole-Y7UJPJUCJWX4')
        self.assert_has_component(components, instance_profile_name, 'aws.iam.instance_profile')
        self.assert_has_relation(relations, instance_profile_name, role_name)
