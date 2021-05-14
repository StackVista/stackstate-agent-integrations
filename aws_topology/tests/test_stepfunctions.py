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
    file_name = "json/stepfunctions/{}_{}.json".format(operation_name, get_params_hash(self.meta.region_name, args))
    try:
        return resource(file_name)
    except Exception:
        error = "API response file not found for operation: {}\n".format(operation_name)
        error += "Parameters:\n{}\n".format(json.dumps(args[1], indent=2, default=str))
        error += "File missing: {}".format(file_name)
        raise Exception(error)


class TestStepFunctions(unittest.TestCase):

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
            "regions": ["eu-west-1"],
        }
        instance.update({"apis_to_run": ["stepfunctions"]})

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

    def test_process_stepfunctions(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        names = resource('json/cloudformation/names.json')

        def get_id(name, region='eu-west-1', stack='stackstate-main-account-main-region'):
            account = '548105126730'
            res = names.get(account + '|' + region + '|' + stack + '|' + name)
            if res:
                arn = type_arn.get(res["type"])
                if arn:
                    return arn(region=region, account_id=account, resource_id=res["id"])

        sfn_id = get_id('StepFunctionsStateMachine')
        self.assert_has_component(components, sfn_id, 'aws.stepfunction.statemachine')
        self.assert_has_component(
            components,
            get_id('StepFunctionsActivity'),
            'aws.stepfunction.activity')
        state_names = [
            "Activity",
            "ApiMap",
            "ApiGateway",
            "FakeChoice",
            "FakeInput",
            "Finish",
            "NoFinish",
            "ParallelRun",
            "ECS",
            "SNS",
            "SQS",
            "SQSSecondaryRegion",
            "DynamoDB",
            "Lambda",
            "LambdaOldVersion"
        ]
        for state_name in state_names:
            self.assert_has_component(components, sfn_id + ':state/' + state_name, 'aws.stepfunction.state')
        self.assertEqual(len(components), len(state_names) + 2)
        # starting state
        self.assert_has_relation(relations, sfn_id, sfn_id + ':state/ParallelRun')
        # parallel branch 1
        self.assert_has_relation(relations, sfn_id + ':state/ParallelRun', sfn_id + ':state/ECS')
        # parallel branch 2
        self.assert_has_relation(relations, sfn_id + ':state/ParallelRun', sfn_id + ':state/SNS')
        if True:
            self.assert_has_relation(relations, sfn_id + ':state/SNS', sfn_id + ':state/SQS')
            self.assert_has_relation(relations, sfn_id + ':state/SQS', sfn_id + ':state/SQSSecondaryRegion')
        # parallel branch 3
        self.assert_has_relation(relations, sfn_id + ':state/ParallelRun', sfn_id + ':state/Lambda')
        if True:
            self.assert_has_relation(relations, sfn_id + ':state/Lambda', sfn_id + ':state/LambdaOldVersion')
            self.assert_has_relation(relations, sfn_id + ':state/LambdaOldVersion', sfn_id + ':state/DynamoDB')

        self.assert_has_relation(relations, sfn_id + ':state/ParallelRun', sfn_id + ':state/FakeInput')
        # iterator
        self.assert_has_relation(relations, sfn_id + ':state/FakeInput', sfn_id + ':state/ApiMap')
        if True:
            self.assert_has_relation(relations, sfn_id + ':state/ApiMap', sfn_id + ':state/ApiGateway')
        # choice
        self.assert_has_relation(relations, sfn_id + ':state/ApiMap', sfn_id + ':state/FakeChoice')
        if True:
            self.assert_has_relation(relations, sfn_id + ':state/FakeChoice', sfn_id + ':state/Finish')
            self.assert_has_relation(relations, sfn_id + ':state/FakeChoice', sfn_id + ':state/Activity')
        # last
        self.assert_has_relation(relations, sfn_id + ':state/Activity', sfn_id + ':state/NoFinish')

        # 15 states

        self.assert_has_relation(relations, sfn_id + ':state/SNS', get_id('SnsTopic'))
        self.assert_has_relation(relations, sfn_id + ':state/SQS', get_id('SqsQueue'))
        self.assert_has_relation(
            relations,
            sfn_id + ':state/SQSSecondaryRegion',
            get_id('SqsQueue', stack='stackstate-main-account-secondary-region', region='us-east-1')
        )
        self.assert_has_relation(relations, sfn_id + ':state/DynamoDB', get_id('DynamoDbTable'))
        # TODO verify if this is OK, it refers to stage here?
        self.assert_has_relation(relations, sfn_id + ':state/ApiGateway', get_id('ApiGatewayApi') + '/test')
        self.assert_has_relation(relations, sfn_id + ':state/Lambda', get_id('LambdaFunction'))
        self.assert_has_relation(relations, sfn_id + ':state/LambdaOldVersion', get_id('LambdaFunction'))
        self.assert_has_relation(relations, sfn_id + ':state/ECS', get_id('EcsTaskDefinition'))
        self.assert_has_relation(relations, sfn_id + ':state/ECS', get_id('EcsCluster'))
        self.assert_has_relation(relations, sfn_id + ':state/Activity', get_id('StepFunctionsActivity'))
        self.assert_has_relation(relations, sfn_id, get_id('StepFunctionsIamRole'))

        self.assertEqual(len(topology[0]["relations"]), 26)
