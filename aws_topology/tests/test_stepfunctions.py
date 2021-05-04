import unittest
import os
import json
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


def mock_boto_calls(operation_name, kwarg=None):
    if operation_name == "AssumeRole":
        return {
            "Credentials": {
                "AccessKeyId": "KEY_ID",
                "SecretAccessKey": "ACCESS_KEY",
                "SessionToken": "TOKEN"
            }
        }
    elif operation_name == 'ListStateMachines':
        return resource('json/stepfunctions/list_state_machines.json')
    elif operation_name == 'DescribeStateMachine':
        return resource('json/stepfunctions/describe_state_machine.json')
    elif operation_name == 'ListActivities':
        return resource('json/stepfunctions/list_activities.json')
    elif operation_name == 'LookupEvents':
        return {}
    raise ValueError("Unknown operation name", operation_name)


class TestStepFunctions(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        self.patcher = patch("botocore.client.BaseClient._make_api_call")
        self.mock_object = self.patcher.start()
        top.reset()
        aggregator.reset()
        init_config = InitConfig({
            "aws_access_key_id": "some_key",
            "aws_secret_access_key": "some_secret",
            "external_id": "disable_external_id_this_is_unsafe"
        })
        instance = {
            "role_arn": "arn:aws:iam::731070500579:role/RoleName",
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

        sfn_id = 'arn:aws:states:eu-west-1:290794210101:stateMachine:StepFunctionsStateMachine-cLtKjmzGLpw8'
        components = topology[0]["components"]
        relations = topology[0]["relations"]
        self.assert_has_component(components, sfn_id, 'aws.stepfunction')
        self.assert_has_component(
            components,
            'arn:aws:states:eu-west-1:290794210101:activity:TestActivity',
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

        # integrations currently 4 (should be 10 since ECS 2x!)
        self.assert_has_relation(
            relations,
            sfn_id + ':state/SNS',
            'arn:aws:sns:eu-west-1:290794210101:elvin-stackstate-tests-main-account-main-region-SnsTopic-1MQ0AIIPHC352'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/SQS',
            'https://sqs.eu-west-1.amazonaws.com/290794210101/'
            + 'elvin-stackstate-tests-main-account-main-region-SqsQueue-12QD0SDWO9WV1'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/SQSSecondaryRegion',
            'https://sqs.us-east-1.amazonaws.com/290794210101/'
            + 'elvin-stackstate-main-account-secondary-region-SqsQueue-142V2KSEY368Y'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/DynamoDB',
            'arn:aws:dynamodb:eu-west-1:731070500579:table/'
            + 'elvin-stackstate-tests-main-account-main-region-DynamoDbTable-16SXEQ30MM5RN'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/ApiGateway',
            'arn:aws:execute-api:eu-west-1:731070500579:z3scu84808/test/GET/test'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/Lambda',
            'arn:aws:lambda:eu-west-1:290794210101:function:'
            + 'elvin-stackstate-tests-main-account-LambdaFunction-199Z59KY5LNOM:$LATEST'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/LambdaOldVersion',
            'arn:aws:lambda:eu-west-1:290794210101:function:'
            + 'elvin-stackstate-tests-main-account-LambdaFunction-199Z59KY5LNOM'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/ECS',
            'arn:aws:ecs:eu-west-1:290794210101:task-definition/'
            + 'elvin-stackstate-tests-main-account-main-region-EcsTaskDefinition-2BeEG06Qwhoq:1'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/ECS',
            'arn:aws:ecs:eu-west-1:290794210101:cluster/'
            + 'elvin-stackstate-tests-main-account-main-region-EcsCluster-QAt7B7u3rss9'
        )
        self.assert_has_relation(
            relations,
            sfn_id + ':state/Activity',
            'arn:aws:states:eu-west-1:290794210101:activity:TestActivity'
        )

        self.assertEqual(len(topology[0]["relations"]), 25)
