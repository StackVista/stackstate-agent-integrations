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


"""
This file does not really contain a test.

It can be used to run against a real account.

It can snapshot API responses.

It uses a 
"""

def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(script_dir, path))


original_method = botocore.client.BaseClient._make_api_call

cnt = 1

def get_params_hash(data):
    return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode('utf-8')).hexdigest()[0:7]

@contextmanager
def mock_patch_method_original(mock_path):

    def side_effect(self, *args, **kwargs):
        global cnt
        side_effect.self = self
        result = original_method(self, *args, **kwargs)
        if "ResponseMetadata" in result:
            result.pop("ResponseMetadata")
        result["ResponseMetadata"] = {
            "Parameters": args[1],
            "OperationName": args[0],
            "Generater": datetime.datetime.now()
        }
        fn = botocore.xform_name(args[0]) + '_' + get_params_hash(args)
        with open(relative_path('json/eventbridge/' + fn + '.json'), 'w') as outfile:
            json.dump(result, outfile, indent=2, default=str)
        cnt += 1
        return result

    patcher = mock.patch(mock_path, autospec=True, side_effect=side_effect)
    yield patcher.start()
    patcher.stop()


class TestEventBridge(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        with open(relative_path('../stackstate_checks/aws_topology.yaml'), 'r') as stream:
            data_loaded = yaml.safe_load(stream)
        top.reset()
        aggregator.reset()
        init_config = InitConfig({
            "aws_access_key_id": data_loaded["init_config"]["aws_access_key_id"],
            "aws_secret_access_key": data_loaded["init_config"]["aws_secret_access_key"],
            "external_id": data_loaded["init_config"]["external_id"]
        })
        instance = {
            "role_arn": data_loaded["instances"][0]["role_arn"],
            "regions": ["eu-west-1"],
        }
        instance.update({"apis_to_run": ['events']})

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

    def test_process_realaccount(self):
        with mock_patch_method_original('botocore.client.BaseClient._make_api_call') as mock:
            self.check.run()
            topology = [top.get_snapshot(self.check.check_id)]
            self.assertEqual(len(topology), 1)
            self.assert_executed_ok()
            components = topology[0]["components"]
            relations = topology[0]["relations"]
            # print('# components: ', len(components))
            # print('# relations: ', len(relations))
            #for component in components:
            #    print(json.dumps(component, indent=2, default=str))
            #for relation in relations:
            #    print(json.dumps(relation, indent=2, default=str))
