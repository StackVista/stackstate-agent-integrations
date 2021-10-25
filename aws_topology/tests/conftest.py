# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import logging

import pytest
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
from datetime import datetime, timedelta
import pytz

REGION = "test-region"
KEY_ID = "1234"
ACCESS_KEY = "5678"
ACCOUNT_ID = "123456789012"
WRONG_ACCOUNT_ID = "987654321012"
ROLE = "some_role_with_many_characters"
TOKEN = "ABCDE"

API_RESULTS = {
    "AssumeRole": {"Credentials": {"AccessKeyId": KEY_ID, "SecretAccessKey": ACCESS_KEY, "SessionToken": TOKEN}},
    "GetCallerIdentity": {
        "Account": ACCOUNT_ID,
    },
}


@pytest.fixture(scope="session")
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
    cfg = {"aws_access_key_id": "abc", "aws_secret_access_key": "cde", "external_id": "randomvalue"}
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


def set_eventbridge_event(value):
    def inner(func):
        func.eventbridge_event = value
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
    return hashlib.md5((region + json.dumps(data, sort_keys=True, default=str)).encode("utf-8")).hexdigest()[0:7]


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


def get_bytes_from_file(path):
    return open(relative_path(path), "rb").read()


def use_gz(value):
    def inner(func):
        func.gz = value
        return func

    return inner


def set_log_bucket_name(value):
    def inner(func):
        func.log_bucket_name = value
        return func

    return inner


def wrapper(api, not_authorized, subdirectory, event_name=None, eventbridge_event_name=None):
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", datefmt="%d-%m-%Y %H:%M:%S",
                        level=logging.DEBUG)

    def mock_boto_calls(self, *args, **kwargs):
        operation_name = botocore.xform_name(args[0])
        if operation_name == "assume_role":
            return {"Credentials": {"AccessKeyId": "KEY_ID", "SecretAccessKey": "ACCESS_KEY", "SessionToken": "TOKEN"}}
        if event_name:
            if operation_name == "lookup_events":
                res = resource("json/" + api + "/cloudtrail/" + event_name + ".json")
                dt = datetime.utcnow() + timedelta(hours=3)
                res["eventTime"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                msg = {"Events": [{"CloudTrailEvent": json.dumps(res)}]}
                return msg
        if eventbridge_event_name:
            if operation_name == "lookup_events":
                return {}
            if operation_name == "get_bucket_versioning":
                return {"Status": "Enabled"}
            if operation_name == "list_objects_v2":
                return {
                    "Contents": [
                        {
                            "Key": "AWSLogs/123456789012/EventBridge/eu-west-1"
                                   + "/2021/06/11/05/stackstate-eventbridge-stream-2-2021-06-11-05-18-05-"
                                   + "b7d5fff3-928a-4e63-939b-1a32662b6a63.gz"
                        }
                    ]
                }
            if operation_name == "get_object":
                res = resource("json/" + api + "/cloudtrail/" + eventbridge_event_name + ".json")
                return {"Body": json.dumps(res)}
        if operation_name in not_authorized:
            # Some APIs return a different error code when there is no permission
            # But there are no docs on which ones do. Here is an array of some known APIs
            if api in ["stepfunctions", "firehose"]:
                error_code = "AccessDeniedException"
            elif api == "ec2":
                error_code = "UnauthorizedOperation"
            elif api == "sns":
                error_code = "AuthorizationError"
            else:
                error_code = "AccessDenied"
            raise ClientError({"Error": {"Code": error_code}}, operation_name)
        apidir = api
        if apidir is None:
            apidir = self._service_model.service_name
        file_name = os.path.join("json", apidir, subdirectory,
                                 "{}_{}.json".format(operation_name, get_params_hash(self.meta.region_name, args)))
        try:
            result = resource(file_name)
            logging.debug('file: %s ', file_name)
            logging.debug('args: %s', json.dumps(args, indent=2, default=str))
            try:
                logging.debug('meta: %s', json.dumps(result["ResponseMetadata"]["Parameters"], indent=2, default=str))
            except KeyError:
                pass
        except Exception:
            error = "API response file not found for operation: {}\n".format(operation_name)
            error += "Parameters:\n{}\n".format(json.dumps(args[1], indent=2, default=str))
            error += "File missing: {}".format(file_name)
            raise Exception(error)
        # If an error code is included in the response metadata, raise this instead
        if "Error" in result.get("ResponseMetadata", {}):
            raise ClientError({"Error": result["ResponseMetadata"]["Error"]}, operation_name)
        else:
            return result

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

    @staticmethod
    def get_filter():
        return ""

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        method = getattr(self, self._testMethodName)
        not_authorized = []
        if hasattr(method, "not_authorized"):
            not_authorized = method.not_authorized
        cloudtrail_event = None
        if hasattr(method, "cloudtrail_event"):
            cloudtrail_event = method.cloudtrail_event
        eventbridge_event = None
        if hasattr(method, "eventbridge_event"):
            eventbridge_event = method.eventbridge_event
        filter = ""
        if hasattr(method, "filter"):
            filter = method.filter
        subdirectory = ""
        if hasattr(method, "subdirectory"):
            subdirectory = method.subdirectory
        self.patcher = patch("botocore.client.BaseClient._make_api_call", autospec=True)
        self.mock_object = self.patcher.start()
        top.reset()
        aggregator.reset()
        init_config = InitConfig(
            {
                "aws_access_key_id": "some_key",
                "aws_secret_access_key": "some_secret",
                "external_id": "disable_external_id_this_is_unsafe",
            }
        )
        regions = self.get_region()
        if not isinstance(regions, list):
            regions = [regions]
        instance = {
            "role_arn": "arn:aws:iam::{}:role/RoleName".format(self.get_account_id()),
            "regions": regions
        }
        api = self.get_api()
        apis = None
        if api:
            if filter:
                apis = [api + "|" + filter]
            else:
                apis = [api]
        if cloudtrail_event:
            apis = []
        instance.update({"apis_to_run": apis})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        self.check.last_full_topology = datetime(2021, 5, 1, 0, 0, 0).replace(tzinfo=pytz.utc)

        def ignore_callback(self, *args, **kwargs):
            return

        self.check.get_flowlog_update = ignore_callback
        if cloudtrail_event is None and eventbridge_event is None:
            self.check.get_topology_update = ignore_callback
        self.mock_object.side_effect = wrapper(
            api, not_authorized, subdirectory, event_name=cloudtrail_event, eventbridge_event_name=eventbridge_event
        )
        self.components_checked = 0
        self.relations_checked = 0

    def tearDown(self):
        self.patcher.stop()

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    def assert_updated_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_UPDATE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    def assert_location_info(self, component):
        self.assertEqual(component["data"]["Location"]["AwsAccount"], self.get_account_id())
        region = self.get_region()
        if component["type"] == "aws.route53.domain" or component["type"] == "aws.route53.hostedzone":
            region = "us-east-1"
        self.assertEqual(component["data"]["Location"]["AwsRegion"], region)
