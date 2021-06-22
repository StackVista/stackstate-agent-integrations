import json
import os
import unittest
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
import botocore
import io
from .conftest import get_params_hash
from functools import reduce


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


def get_bytes_from_file(path):
    return open(relative_path(path), "rb").read()


def use_subdirectory(value):
    def inner(func):
        func.subdirectory = value
        return func

    return inner


def use_gz(value):
    def inner(func):
        func.gz = value
        return func

    return inner


def set_not_authorized(value):
    def inner(func):
        func.not_authorized = value
        return func

    return inner


def set_log_bucket_name(value):
    def inner(func):
        func.log_bucket_name = value
        return func

    return inner


def wrapper(testinstance, not_authorized, subdirectory, use_gz, events_file=None):
    api = "flowlogs"
    instance = testinstance

    def mock_boto_calls(self, *args, **kwargs):
        if args[0] == "AssumeRole":
            return {"Credentials": {"AccessKeyId": "KEY_ID", "SecretAccessKey": "ACCESS_KEY", "SessionToken": "TOKEN"}}
        operation_name = botocore.xform_name(args[0])
        instance.recorder.append({"operation_name": operation_name, "parameters": args[1]})
        if operation_name == "delete_objects":
            return {}
        if operation_name in not_authorized:
            raise botocore.exceptions.ClientError({"Error": {"Code": "AccessDenied"}}, operation_name)
        apidir = api
        directory = os.path.join("json", apidir, subdirectory)
        ext = "gz" if use_gz and operation_name == "get_object" else "json"
        file_name = "{}/{}_{}.{}".format(directory, operation_name, get_params_hash(self.meta.region_name, args), ext)
        try:
            if ext == "gz":
                b = get_bytes_from_file(file_name)
                result = {"Body": botocore.response.StreamingBody(io.BytesIO(b), len(b))}
            else:
                result = resource(file_name)
            # print('file: ', file_name)
            # print('args: ', json.dumps(args, indent=2, default=str))
            # print('meta: ', json.dumps(result["ResponseMetadata"]["Parameters"], indent=2, default=str))
        except Exception:
            error = "API response file not found for operation: {}\n".format(operation_name)
            error += "Parameters:\n{}\n".format(json.dumps(args[1], indent=2, default=str))
            error += "File missing: {}".format(file_name)
            raise Exception(error)
        # If an error code is included in the response metadata, raise this instead
        if "Error" in result.get("ResponseMetadata", {}):
            raise botocore.exceptions.ClientError(
                {"Error": {"Code": result["ResponseMetadata"]["Error"]}}, operation_name
            )
        else:
            return result

    return mock_boto_calls


class TestFlowLogs(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def get_region(self):
        return ["eu-west-1"]

    def get_account_id(self):
        return "123456789012"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        self.recorder = []
        method = getattr(self, self._testMethodName)
        not_authorized = []
        if hasattr(method, "not_authorized"):
            not_authorized = method.not_authorized
        events_file = None
        if hasattr(method, "events_file"):
            events_file = method.events_file
        subdirectory = ""
        if hasattr(method, "subdirectory"):
            subdirectory = method.subdirectory
        log_bucket_name = ""
        if hasattr(method, "log_bucket_name"):
            log_bucket_name = method.log_bucket_name
        use_gz = False
        if hasattr(method, "gz"):
            use_gz = method.gz
        self.patcher = patch("botocore.client.BaseClient._make_api_call", autospec=True)
        self.extrapatch = patch("stackstate_checks.aws_topology.AwsTopologyCheck.must_run_full", return_value=False)
        self.mock_object = self.patcher.start()
        self.extrapatch.start()

        top.reset()
        aggregator.reset()
        init_config = InitConfig(
            {
                "aws_access_key_id": "some_key",
                "aws_secret_access_key": "some_secret",
                "external_id": "disable_external_id_this_is_unsafe",
                "process_flow_logs": True
            }
        )
        regions = self.get_region()
        if not isinstance(regions, list):
            regions = [regions]
        instance = {
            "role_arn": "arn:aws:iam::{}:role/RoleName".format(self.get_account_id()),
            "regions": regions,
            "state": {"last_full_topology": "2021-05-01T00:00:00"},
        }
        if log_bucket_name:
            instance.update({"log_bucket_name": log_bucket_name})
        apis = []
        instance.update({"apis_to_run": apis})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        state_descriptor = self.check._get_state_descriptor()
        # clear the state
        self.check.state_manager.clear(state_descriptor)
        self.mock_object.side_effect = wrapper(self, not_authorized, subdirectory, use_gz, events_file=events_file)

    def tearDown(self):
        self.patcher.stop()
        self.extrapatch.stop()

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    def test_process_flowlogs(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        self.assertEqual(len(components), 2)
        self.assertEqual(len(relations), 1)
        self.assertEqual(
            components[0],
            {
                "id": "urn:vpcip:vpc-0305206adbbda9918/10.16.133.15",
                "data": {
                    "Location": {"AwsAccount": "123456789012", "AwsRegion": "eu-west-1"},
                    "URN": ["urn:vpcip:vpc-0305206adbbda9918/10.16.133.15"],
                    "tags": ["integration-type:aws-v2", "integration-url:123456789012"],
                },
                "type": "vpc.request",
            },
        )
        self.assertEqual(
            components[1],
            {
                "id": "urn:vpcip:vpc-0305206adbbda9918/10.16.5.72",
                "data": {
                    "Location": {"AwsAccount": "123456789012", "AwsRegion": "eu-west-1"},
                    "URN": ["urn:vpcip:vpc-0305206adbbda9918/10.16.5.72"],
                    "tags": ["integration-type:aws-v2", "integration-url:123456789012"],
                },
                "type": "vpc.request",
            },
        )
        self.assertEqual(
            relations[0],
            {
                "data": {},
                "source_id": "urn:vpcip:vpc-0305206adbbda9918/10.16.133.15",
                "target_id": "urn:vpcip:vpc-0305206adbbda9918/10.16.5.72",
                "type": "uses service",
            },
        )
        dels = filter(lambda x: x["operation_name"] == "delete_objects", self.recorder)

        def get_keys(acc, lst):
            for obj in lst["parameters"]["Delete"]["Objects"]:
                acc.append(obj["Key"])
            return acc

        dels = reduce(get_keys, dels, [])

        self.assertEqual(
            dels,
            [
                "AWSLogs/120431062118/vpcflowlogs/eu-west-1/2021/04/01/120431062118"
                + "_vpcflowlogs_eu-west-1_fl-0630869f236e76872_20210401T0000Z_ea4b0f55.log.gz",
                "AWSLogs/120431062118/vpcflowlogs/eu-west-1/2021/06/22/120431062118"
                + "_vpcflowlogs_eu-west-1_fl-0630869f236e76872_20210622T0000Z_ea4b0f55.log.gz",
            ],
        )
