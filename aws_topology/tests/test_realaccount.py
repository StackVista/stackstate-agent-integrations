import unittest
import os
import json
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
import yaml


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(script_dir, path))

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
            "regions": ["global"],  # "global", "eu-west-1", "us-east-1"
        }
        instance.update({"apis_to_run": ['iam']})  # apigatewayv2

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
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        components = topology[0]["components"]
        relations = topology[0]["relations"]
        print('# components: ', len(components))
        print('# relations: ', len(relations))
        #for component in components:
        #    print(json.dumps(component, indent=2, default=str))
        #for relation in relations:
        #    print(json.dumps(relation, indent=2, default=str))
