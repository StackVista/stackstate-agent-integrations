import unittest
import os
import json
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
import botocore
import hashlib
from stackstate_checks.aws_topology.resources.cloudformation import type_arn
from stackstate_checks.aws_topology.resources.stepfunction import StepFunctionCollector


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
    if args[0] == "LookupEvents":
        return {}
    operation_name = botocore.xform_name(args[0])
    file_name = "json/stepfunctions/{}_{}.json".format(operation_name, get_params_hash(self.meta.region_name, args))
    try:
        return resource(file_name)
    except Exception:
        error = "API response file not found for operation: {}\n".format(operation_name)
        error += "Parameters:\n{}\n".format(json.dumps(args[1], indent=2, default=str))
        error += "File missing: {}".format(file_name)
        raise Exception(error)


class AgentMock(object):
    def __init__(self):
        self.components = []
        self.relations = []
        self.warnings = []

    def relation(self, source, target, relation_type, data):
        self.relations.append({
            'source_id': source,
            'target_id': target,
            'type': relation_type,
            'data': data
        })

    def component(self, loc, id, component_type, data):
        self.components.append({
            'id': id,
            'type': component_type,
            'data': data
        })

    def warning(self, txt):
        self.warnings.append(txt)

    def create_arn(self, type, loc, resource_id):
        return 'arn:' + type + ':' + resource_id


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

    def test_process_stepfunctions(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        names = resource('json/cloudformation/names.json')  # TODO move file to stepfunctions (=snapshot)

        def get_id(name, region='eu-west-1', stack='stackstate-main-account-main-region'):
            account = '548105126730'
            res = names.get(account + '|' + region + '|' + stack + '|' + name)
            if res:
                if not res["id"].startswith('arn:aws:'):
                    arn = type_arn.get(res["type"])
                    if arn:
                        return arn(region=region, account_id=account, resource_id=res["id"])
                    else:
                        return "UNSUPPORTED_ARN-" + res["type"] + "-" + res["id"]
                else:
                    return res["id"]

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
        # TODO ApiGatewayV2 not yet supported (SO RELATION LEFT ALERTER)
        # TODO also verify if this is OK to refer to the API stage here?
        self.assertIn('UNSUPPORTED_ARN-AWS::ApiGatewayV2::', get_id('ApiGatewayApi') + '/test')
        # self.assert_has_relation(relations, sfn_id + ':state/ApiGateway', get_id('ApiGatewayApi') + '/test')

        self.assert_has_relation(relations, sfn_id + ':state/Lambda', get_id('LambdaFunction'))
        self.assert_has_relation(relations, sfn_id + ':state/LambdaOldVersion', get_id('LambdaFunction'))
        self.assert_has_relation(relations, sfn_id + ':state/ECS', get_id('EcsTaskDefinition'))
        self.assert_has_relation(relations, sfn_id + ':state/ECS', get_id('EcsCluster'))
        self.assert_has_relation(relations, sfn_id + ':state/Activity', get_id('StepFunctionsActivity'))
        # TODO IAM not yet supported (SO RELATION LEFT ALERTER)
        self.assertIn('UNSUPPORTED_ARN-AWS::IAM::', get_id('StepFunctionsIamRole'))
        # self.assert_has_relation(relations, sfn_id, get_id('StepFunctionsIamRole'))

        self.assertEqual(len(topology[0]["relations"]), 26)

    def test_process_stepfunction_branch_state(self):
        location_info = {
            'Location': {
                'AwsRegion': 'test',
                'AwsAccount': 'acct'
            }
        }
        branches = [
            {
                'StartAt': 'B1S1',
                'States': {
                    'B1S1': {
                        'Next': 'B1S2'
                    },
                    'B1S2': {
                        'Type': 'Parallel',
                        'Branches': [
                            {
                                'StartAt': 'B3S1',
                                'States': {
                                    'B3S1': {
                                    }
                                }
                            }
                        ]
                    }
                }
            },
            {
                'StartAt': 'B2S1',
                'States': {
                    'B2S1': {
                        'Next': 'B2S2'
                    },
                    'B2S2': {
                    }
                }
            }
        ]
        expected_relations = [
            {'source_id': 'brancharn', 'target_id': 'root:state/B1S1', 'type': 'uses service', 'data': {}},
            {'source_id': 'brancharn', 'target_id': 'root:state/B2S1', 'type': 'uses service', 'data': {}},
            {'source_id': 'root:state/B1S1', 'target_id': 'root:state/B1S2', 'type': 'uses service', 'data': {}},
            {'source_id': 'root:state/B2S1', 'target_id': 'root:state/B2S2', 'type': 'uses service', 'data': {}},
            {'source_id': 'root:state/B1S2', 'target_id': 'root:state/B3S1', 'type': 'uses service', 'data': {}},
        ]
        expected_components = [
            {'id': 'root:state/B1S1', 'type': 'aws.stepfunction.state'},
            {'id': 'root:state/B3S1', 'type': 'aws.stepfunction.state'},
            {'id': 'root:state/B1S2', 'type': 'aws.stepfunction.state'},
            {'id': 'root:state/B2S1', 'type': 'aws.stepfunction.state'},
            {'id': 'root:state/B2S2', 'type': 'aws.stepfunction.state'}]
        agent = AgentMock()
        collector = StepFunctionCollector(location_info, None, agent)
        collector.process_parallel_state('root', 'brancharn', branches)
        self.assertEqual(len(agent.relations), len(expected_relations))
        for relation in expected_relations:
            self.assertIn(relation, agent.relations)
        for component in agent.components:
            del component['data']
        self.assertEqual(len(agent.components), len(expected_components))
        for component in expected_components:
            self.assertIn(component, agent.components)

    def test_process_stepfunction_task_state(self):
        location_info = {
            'Location': {
                'AwsRegion': 'test',
                'AwsAccount': 'acct'
            }
        }
        nameonly_prefix = "arn:AWS::Lambda::Function:"
        arn_prefix = "arn:aws:lambda:region:account:function:"
        partial_prefix = "123456789012:function:"
        lambda_refs = [
            # name only
            {'ref': 'one',         'expected': nameonly_prefix + 'one'},
            {'ref': 'one:alias',   'expected': nameonly_prefix + 'one:alias'},
            {'ref': 'one:1',       'expected': nameonly_prefix + 'one'},
            {'ref': 'one:$latest', 'expected': nameonly_prefix + 'one'},
            # arn
            {'ref': arn_prefix + 'one',         'expected': arn_prefix + 'one'},
            {'ref': arn_prefix + 'one:alias',   'expected': arn_prefix + 'one:alias'},
            {'ref': arn_prefix + 'one:1',       'expected': arn_prefix + 'one'},
            {'ref': arn_prefix + 'one:$latest', 'expected': arn_prefix + 'one'},
            # partial
            {'ref': partial_prefix + 'one',         'expected': nameonly_prefix + 'one'},
            {'ref': partial_prefix + 'one:alias',   'expected': nameonly_prefix + 'one:alias'},
            {'ref': partial_prefix + 'one:1',       'expected': nameonly_prefix + 'one'},
            {'ref': partial_prefix + 'one:$latest', 'expected': nameonly_prefix + 'one'},
        ]
        for lambda_ref in lambda_refs:
            agent = AgentMock()
            collector = StepFunctionCollector(location_info, None, agent)
            state = {
                'Type': 'Task',
                'Resource': 'arn:aws:states:::lambda:',
                'Parameters': {
                    'FunctionName': lambda_ref['ref']
                }
            }
            collector.process_task_state('rootstate', state)
            self.assertEqual(agent.relations[0]["target_id"], lambda_ref["expected"], lambda_ref["ref"])
        wrong_refs = [
            # name only
            {'ref': '1:2:3:4:5:6:7:8:9'},
            {'ref': '1:2:3:4:5'},
            {'ref': '1:2:3:4:5:6'},
        ]
        for lambda_ref in wrong_refs:
            agent = AgentMock()
            collector = StepFunctionCollector(location_info, None, agent)
            state = {
                'Type': 'Task',
                'Resource': 'arn:aws:states:::lambda:',
                'Parameters': {
                    'FunctionName': lambda_ref['ref']
                }
            }
            collector.process_task_state('rootstate', state)
            self.assertIn("Could not make lambda relation of " + lambda_ref["ref"], agent.warnings)
