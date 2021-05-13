import unittest
import os
import json
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
import re
import botocore
import hashlib


def get_params_hash(region, data):
    return hashlib.md5((region + json.dumps(data, sort_keys=True, default=str)).encode('utf-8')).hexdigest()[0:7]


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


def mock_boto_calls(self, *args, **kwargs):
    if args[0] == "AssumeRole":
        return {
            "Credentials": {
                "AccessKeyId": "KEY_ID",
                "SecretAccessKey": "ACCESS_KEY",
                "SessionToken": "TOKEN"
            }
        }
    operation_name = botocore.xform_name(args[0])
    file_name = "json/iam/{}_{}.json".format(operation_name, get_params_hash(self.meta.region_name, args))
    try:
        return resource(file_name)
    except Exception:
        error = "API response file not found for operation: {}\n".format(operation_name)
        error += "Parameters:\n{}\n".format(json.dumps(args[1], indent=2, default=str))
        error += "File missing: {}".format(file_name)
        raise Exception(error)


class TestIAM(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        self.patcher = patch("botocore.client.BaseClient._make_api_call", autospec=True)
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

        def find_id(type, name, get_arn=get_arn):
            found = 0
            result = None
            rgex = re.compile('^' + get_arn(type, name)+'-[A-Z0-9]{12,14}$')
            for component in components:
                if rgex.match(component["id"]):
                    result = component["id"]
                    found += 1
            if found > 1:
                raise Exception('Multiple found matching {}'.format(get_arn(type, name) + '-ABCDEFGH123'))
            if found == 0:
                raise Exception('Not found {}'.format(get_arn(type, name) + '-ABCDEFGH123'))
            return result

        user_name = find_id('user', 'IamUser')
        group_name = find_id('group', 'IamGroup')
        user_inline_policy_name = user_name + ':inlinepolicy/default'
        group_inline_policy_name = group_name + ':inlinepolicy/default'
        attached_policy_name = find_id('policy', 'IamPolicy1')
        user_boundary_policy = find_id('policy', 'IamPolicy2')
        self.assert_has_component(components, user_name, 'aws.iam.user')
        self.assert_has_relation(relations, user_name, group_name)
        self.assert_has_relation(relations, user_name, user_inline_policy_name)
        self.assert_has_relation(relations, user_name, attached_policy_name)
        self.assert_has_relation(relations, group_name, group_inline_policy_name)
        self.assert_has_relation(relations, group_name, attached_policy_name)
        self.assert_has_relation(relations, user_name, user_boundary_policy)

        role_name = find_id('role', 'LambdaFunctionIamRole', get_arn=get_main_arn)
        role_attached_policy_name = find_id('policy', 'LambdaFunctionIamPolicy1')
        role_inline_policy_name = role_name + ':inlinepolicy/lambda'
        self.assert_has_component(components, role_name, 'aws.iam.role')
        self.assert_has_component(components, role_attached_policy_name, 'aws.iam.policy')
        self.assert_has_relation(relations, role_name, role_attached_policy_name)
        self.assert_has_relation(relations, role_name, role_inline_policy_name)
        self.assert_has_relation(relations, role_name, 'arn:aws:iam::aws:policy/AdministratorAccess')

        instance_profile_name = find_id('instance-profile', 'EcsEc2InstanceProfile')
        role_name = find_id('role', 'EcsEc2IamRole')
        self.assert_has_component(components, instance_profile_name, 'aws.iam.instance_profile')
        self.assert_has_relation(relations, instance_profile_name, role_name)
