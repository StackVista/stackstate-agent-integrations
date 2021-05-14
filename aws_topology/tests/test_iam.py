import unittest
import os
import json
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
import botocore
from botocore.exceptions import ClientError
import hashlib
from stackstate_checks.aws_topology.resources.cloudformation import type_arn


def get_params_hash(region, data):
    return hashlib.md5((region + json.dumps(data, sort_keys=True, default=str)).encode('utf-8')).hexdigest()[0:7]


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


def set_not_authorized(value):
    def inner(func):
        func.not_authorized = value
        return func

    return inner


def wrapper(not_authorized):
    def mock_boto_calls(self, *args, **kwargs):
        if args[0] == "AssumeRole":
            return {
                "Credentials": {
                    "AccessKeyId": "KEY_ID",
                    "SecretAccessKey": "ACCESS_KEY",
                    "SessionToken": "TOKEN"
                }
            }
        if args[0] == "LookupEvents":
            return {}
        operation_name = botocore.xform_name(args[0])
        if operation_name in not_authorized:
            raise botocore.exceptions.ClientError({
                'Error': {
                    'Code': 'AccessDenied'
                }
            }, operation_name)
        file_name = "json/iam/{}_{}.json".format(operation_name, get_params_hash(self.meta.region_name, args))
        try:
            return resource(file_name)
        except Exception:
            error = "API response file not found for operation: {}\n".format(operation_name)
            error += "Parameters:\n{}\n".format(json.dumps(args[1], indent=2, default=str))
            error += "File missing: {}".format(file_name)
            raise Exception(error)
    return mock_boto_calls


class TestIAM(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        method = getattr(self, self._testMethodName)
        not_authorized = []
        if hasattr(method, 'not_authorized'):
            not_authorized = method.not_authorized
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
        self.mock_object.side_effect = wrapper(not_authorized)

    def tearDown(self):
        self.patcher.stop()

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

        names = resource('json/cloudformation/names.json')

        def get_id(name):
            account = '548105126730'
            region = 'eu-west-1'
            stack = 'stackstate-main-account-main-region'
            res = names.get(account + '|' + region + '|' + stack + '|' + name)
            if res:
                arn = type_arn.get(res["type"])
                if arn:
                    return arn(region=region, account_id=account, resource_id=res["id"])

        user_name = get_id('IamUser')
        group_name = get_id('IamGroup')
        user_inline_policy_name = user_name + ':inlinepolicy/default'
        group_inline_policy_name = group_name + ':inlinepolicy/default'
        attached_policy_name = get_id('IamPolicy1')
        user_boundary_policy = get_id('IamPolicy2')
        self.assert_has_component(components, user_name, 'aws.iam.user')
        self.assert_has_relation(relations, user_name, group_name)
        self.assert_has_relation(relations, user_name, user_inline_policy_name)
        self.assert_has_relation(relations, user_name, attached_policy_name)
        self.assert_has_relation(relations, group_name, group_inline_policy_name)
        self.assert_has_relation(relations, group_name, attached_policy_name)
        self.assert_has_relation(relations, user_name, user_boundary_policy)

        role_name = get_id('LambdaFunctionIamRole')
        role_attached_policy_name = get_id('LambdaFunctionIamPolicy1')
        role_inline_policy_name = role_name + ':inlinepolicy/lambda'
        self.assert_has_component(components, role_name, 'aws.iam.role')
        self.assert_has_component(components, role_attached_policy_name, 'aws.iam.policy')
        self.assert_has_relation(relations, role_name, role_attached_policy_name)
        self.assert_has_relation(relations, role_name, role_inline_policy_name)
        self.assert_has_relation(relations, role_name, 'arn:aws:iam::aws:policy/AdministratorAccess')

        instance_profile_name = get_id('EcsEc2InstanceProfile')
        role_name = get_id('EcsEc2IamRole')
        self.assert_has_component(components, instance_profile_name, 'aws.iam.instance_profile')
        self.assert_has_relation(relations, instance_profile_name, role_name)

    @set_not_authorized('get_account_authorization_details')
    def test_iam_access(self):
        self.check.run()
        self.assertIn(
            'Role arn:aws:iam::548105126730:role/RoleName needs iam:GetAccountAuthorizationDetails'
                + ' was encountered 1 time(s).',
            self.check.warnings
        )
