# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import unittest
import os
import json
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
from functools import reduce
import botocore
import hashlib
import datetime


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


@pytest.fixture(scope='session')
def sts_environment():
    #  This conf instance is used when running `checksdev env start mycheck myenv`.
    #  The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    #  If you want to run an environment this object can not be empty.
    return {
        "role_arn": "arn:aws:iam::123456789012:role/RoleName",
        "regions": ["eu-west-1"],
    }


@pytest.fixture(scope="class")
def instance(request):
    cfg = {
            "role_arn": "arn:aws:iam::123456789012:role/RoleName",
            "regions": ["eu-west-1"],
    }
    request.cls.instance = cfg


@pytest.fixture(scope="class")
def init_config(request):
    cfg = {
        "aws_access_key_id": "abc",
        "aws_secret_access_key": "cde",
        "external_id": "randomvalue"
    }
    request.cls.config = cfg


@pytest.fixture(scope="class")
def init_config_override(request):
    cfg = {
        "aws_access_key_id": "abc",
        "aws_secret_access_key": "cde",
        "external_id": "disable_external_id_this_is_unsafe",
    }
    request.cls.config = cfg


def set_not_authorized(value):
    def inner(func):
        func.not_authorized = value
        return func

    return inner


def set_cloudtrail_event(value):
    def inner(func):
        func.cloudtrail_event = value
        return func

    return inner


def set_filter(value):
    def inner(func):
        func.filter = value
        return func

    return inner


def use_subdirectory(value):
    def inner(func):
        func.subdirectory = value
        return func

    return inner


def get_params_hash(region, data):
    return hashlib.md5((region + json.dumps(data, sort_keys=True, default=str)).encode('utf-8')).hexdigest()[0:7]


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


def wrapper(api, not_authorized, subdirectory, event_name=None):
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
            if (event_name):
                res = resource("json/" + api + "/cloudtrail/" + event_name + ".json")
                res['eventTime'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                msg = {
                    "Events": [
                        {
                            "CloudTrailEvent": json.dumps(res)
                        }
                    ]
                }
                return msg
            else:
                return {}
        operation_name = botocore.xform_name(args[0])
        if operation_name in not_authorized:
            raise botocore.exceptions.ClientError({
                'Error': {
                    'Code': 'AccessDenied'
                }
            }, operation_name)
        directory = os.path.join("json", api, subdirectory)
        file_name = "{}/{}_{}.json".format(directory, operation_name, get_params_hash(self.meta.region_name, args))
        try:
            result = resource(file_name)
            # print('file: ', file_name)
            # print('args: ', json.dumps(args, indent=2, default=str))
            # print('meta: ', json.dumps(result["ResponseMetadata"]["Parameters"], indent=2, default=str))
            return result
        except Exception:
            error = "API response file not found for operation: {}\n".format(operation_name)
            error += "Parameters:\n{}\n".format(json.dumps(args[1], indent=2, default=str))
            error += "File missing: {}".format(file_name)
            raise Exception(error)
    return mock_boto_calls


class BaseApiTest(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def get_api(self):
        raise NotImplementedError

    def get_account_id(self):
        return "123456789012"

    def get_region(self):
        return "eu-west-1"

    def get_filter(self):
        return ""

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        method = getattr(self, self._testMethodName)
        not_authorized = []
        if hasattr(method, 'not_authorized'):
            not_authorized = method.not_authorized
        cloudtrail_event = None
        if hasattr(method, 'cloudtrail_event'):
            cloudtrail_event = method.cloudtrail_event
        filter = ''
        if hasattr(method, 'filter'):
            filter = method.filter
        subdirectory = ''
        if hasattr(method, 'subdirectory'):
            subdirectory = method.subdirectory
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
            "role_arn": "arn:aws:iam::{}:role/RoleName".format(self.get_account_id()),
            "regions": [self.get_region()],
        }
        api = self.get_api()
        if api:
            if filter:
                apis = [api + '|' + filter]
            else:
                apis = [api]
        if cloudtrail_event:
            apis = []
        instance.update({"apis_to_run": apis})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        self.mock_object.side_effect = wrapper(api, not_authorized, subdirectory, event_name=cloudtrail_event)
        self.components_checked = 0
        self.relations_checked = 0

    def tearDown(self):
        self.patcher.stop()

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    def assert_has_component(self, components, id, type, checks={}):
        self.components_checked += 1
        comp = None
        for component in components:
            if component["id"] == id and component["type"] == type:
                comp = component
                break
        if comp is None:
            print("Components found:")
            for component in components:
                print("{} ({})".format(component.get("id"), component.get("type")))
        self.assertIsNotNone(comp, "Component expected id={} type={}".format(id, type))
        for key in checks:
            self.assertEqual(reduce(dict.__getitem__, ('data.' + key).split('.'), comp), checks[key])
        return comp

    def assert_has_relation(self, relations, source_id, target_id, type=None, checks={}):
        self.relations_checked += 1
        rel = None
        for relation in relations:
            if relation["source_id"] == source_id and relation["target_id"] == target_id:
                rel = relation
                break
        if rel is None:
            print("Relations found:")
            for relation in relations:
                print("{} <-> {}".format(relation.get("source_id"), relation.get("target_id")))
        self.assertIsNotNone(rel, "Relation expected source_id={} target_id={}".format(source_id, target_id))
        if type:
            self.assertEqual(rel["type"], type)
        for key in checks:
            self.assertEqual(reduce(dict.__getitem__, ('data.' + key).split('.'), rel), checks[key])
        return rel

    def assert_location_info(self, component):
        self.assertEqual(component["data"]["Location"]["AwsAccount"], self.get_account_id())
        if component["type"] == "aws.route53.domain":
            self.assertEqual(component["data"]["Location"]["AwsRegion"], "us-east-1")
        elif component["type"] == "aws.route53.hostedzone":
            self.assertEqual(component["data"]["Location"]["AwsRegion"], "us-east-1")
        else:
            self.assertEqual(component["data"]["Location"]["AwsRegion"], self.get_region())
