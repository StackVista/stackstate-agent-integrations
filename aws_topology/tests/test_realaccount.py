import unittest
import os
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
import yaml
import json
import mock
from contextlib import contextmanager
import botocore
import hashlib
import datetime
import glob
import socket


"""
This file does not really contain a test.

It can be used to run against a real account.

It can snapshot API responses.

It uses a
"""


# target = "cloudformation"
# target = "iam"
# target = "events"
# target = "stepfunctions"
# target = "apigatewayv2"
# target = "cloudfront"
target = "redshift"

regions = ["eu-west-1"]
if target == "cloudformation":
    regions = ["eu-west-1", "us-east-1"]
if target == "iam" or target == "cloudfront":
    regions = ["global"]


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(script_dir, path))


original_method = botocore.client.BaseClient._make_api_call
account_id = ""


def get_params_hash(region, data):
    return hashlib.md5((region + json.dumps(data, sort_keys=True, default=str)).encode("utf-8")).hexdigest()[0:7]


@contextmanager
def mock_patch_method_original(mock_path):
    def side_effect(self, *args, **kwargs):
        global account_id
        side_effect.self = self
        result = original_method(self, *args, **kwargs)
        if "ResponseMetadata" in result:
            result.pop("ResponseMetadata")
        result["ResponseMetadata"] = {
            "Parameters": args[1],
            "OperationName": args[0],
            "Generater": datetime.datetime.now(),
            "Region": self.meta.region_name,
            "Account": account_id,
        }
        fn = botocore.xform_name(args[0]) + "_" + get_params_hash(self.meta.region_name, args)
        if args[0] != "AssumeRole":
            with open(relative_path("json/" + target + "/" + fn + ".json"), "w") as outfile:
                json.dump(result, outfile, indent=2, default=str)
        return result

    patcher = mock.patch(mock_path, autospec=True, side_effect=side_effect)
    yield patcher.start()
    patcher.stop()


def get_ipv4_by_hostname(hostname):
    # see `man getent` `/ hosts `
    # see `man getaddrinfo`

    return set(
        i[4][0]  # raw socket structure  # internet protocol info  # address
        for i in socket.getaddrinfo(hostname, 0)  # port, required
    )


class TestEventBridge(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        global account_id
        with open(relative_path("../stackstate_checks/aws_topology.yaml"), "r") as stream:
            data_loaded = yaml.safe_load(stream)
        top.reset()
        aggregator.reset()
        init_config = InitConfig(
            {
                "aws_access_key_id": data_loaded["init_config"]["aws_access_key_id"],
                "aws_secret_access_key": data_loaded["init_config"]["aws_secret_access_key"],
                "external_id": data_loaded["init_config"]["external_id"],
            }
        )
        role = data_loaded["instances"][0]["role_arn"]
        account_id = role.split(":")[4]
        instance = {
            "role_arn": role,
            "regions": regions,
        }
        instance.update({"apis_to_run": ["redshift"]})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])

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

    def xtest_process_realaccount(self):
        with mock_patch_method_original("botocore.client.BaseClient._make_api_call"):
            self.check.run()
            topology = [top.get_snapshot(self.check.check_id)]
            self.assertEqual(len(topology), 1)
            self.assert_executed_ok()

            if target == "ec2":
                print("results")
                components = topology[0]["components"]
                relations = topology[0]["relations"]
                for component in components:
                    print(json.dumps(component, indent=2, default=str))
                for relation in relations:
                    print(json.dumps(relation, indent=2, default=str))
                for rds in components:
                    if rds["type"] == "aws.rds_instance":
                        endpoint = rds["data"]["Endpoint"]["Address"]
                        print("Looking up", endpoint)
                        rips = get_ipv4_by_hostname(endpoint)
                        print("IP", get_ipv4_by_hostname(endpoint))
                        for component in components:
                            if component["type"] == "aws.ec2.networkinterface":
                                if rds["data"]["DBSubnetGroup"].get("VpcId") == component["data"]["VpcId"]:
                                    ips = set([x["PrivateIpAddress"] for x in component["data"]["PrivateIpAddresses"]])
                                    if ips & rips:
                                        print("match", rips)

                for component in components:
                    if component["type"] == "aws.ec2.networkinterface":
                        if component["data"]["InterfaceType"] == "lambda":
                            for lmb in components:
                                if lmb["type"] == "aws.lambda":
                                    if lmb["data"].get("VpcConfig"):
                                        if lmb["data"]["VpcConfig"].get("VpcId"):
                                            if lmb["data"]["VpcConfig"].get("VpcId") == component["data"]["VpcId"]:
                                                if (
                                                    component["data"]["SubnetId"]
                                                    in lmb["data"]["VpcConfig"]["SubnetIds"]
                                                ):
                                                    if set(lmb["data"]["VpcConfig"]["SecurityGroupIds"]) == set(
                                                        [x["GroupId"] for x in component["data"].get("Groups")]
                                                    ):
                                                        print(lmb["id"], component["id"])
                                            else:
                                                print("no match")

            if target == "cloudformation":
                names = {}
                for file in glob.glob(relative_path("json/cloudformation/describe_stack_resources*.json")):
                    with open(file) as f:
                        x = json.load(f)
                        region = x["ResponseMetadata"]["Region"]
                        if x["StackResources"]:
                            for resource in x["StackResources"]:
                                key = "{}|{}|{}|{}".format(
                                    account_id, region, resource["StackName"], resource["LogicalResourceId"]
                                )
                                names[key] = {"type": resource["ResourceType"], "id": resource["PhysicalResourceId"]}
                with open(relative_path("json/cloudformation/names.json"), "w") as outfile:
                    json.dump(names, outfile, indent=2, default=str)
