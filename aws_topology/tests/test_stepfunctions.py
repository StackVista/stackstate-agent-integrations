import os
import json
from stackstate_checks.base.stubs import topology as top
from stackstate_checks.aws_topology.resources.cloudformation import type_arn
from stackstate_checks.aws_topology.resources.stepfunction import StepFunctionCollector
from stackstate_checks.aws_topology.utils import location_info
from collections import Counter
from .conftest import BaseApiTest, set_not_authorized, set_cloudtrail_event


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


class AgentMock(object):
    def __init__(self):
        self.components = []
        self.relations = []
        self.warnings = []

    def relation(self, source, target, relation_type, data):
        self.relations.append({"source_id": source, "target_id": target, "type": relation_type, "data": data})

    def component(self, loc, id, component_type, data):
        self.components.append({"id": id, "type": component_type, "data": data})

    def warning(self, txt):
        self.warnings.append(txt)

    def create_arn(self, type, loc, resource_id):
        return "arn:" + type + ":" + resource_id


class TestStepFunctions(BaseApiTest):
    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def get_api(self):
        return "stepfunctions"

    def get_account_id(self):
        return "548105126730"

    def test_process_stepfunctions(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        names = resource("json/cloudformation/names.json")  # TODO move file to stepfunctions (=snapshot)

        def get_id(name, region="eu-west-1", stack="stackstate-main-account-main-region"):
            account = "548105126730"
            res = names.get(account + "|" + region + "|" + stack + "|" + name)
            if res:
                if not res["id"].startswith("arn:aws:"):
                    arn = type_arn.get(res["type"])
                    if arn:
                        return arn(region=region, account_id=account, resource_id=res["id"])
                    else:
                        return "UNSUPPORTED_ARN-" + res["type"] + "-" + res["id"]
                else:
                    return res["id"]

        sfn_id = get_id("StepFunctionsStateMachine")
        top.assert_component(components, sfn_id, "aws.stepfunction.statemachine")
        top.assert_component(components, get_id("StepFunctionsActivity"), "aws.stepfunction.activity")
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
            "LambdaOldVersion",
        ]
        for state_name in state_names:
            top.assert_component(components, sfn_id + ":state/" + state_name, "aws.stepfunction.state")
        # starting state
        top.assert_relation(relations, sfn_id, sfn_id + ":state/ParallelRun", "uses-service")
        # parallel branch 1
        top.assert_relation(relations, sfn_id + ":state/ParallelRun", sfn_id + ":state/ECS", "uses-service")
        # parallel branch 2
        top.assert_relation(relations, sfn_id + ":state/ParallelRun", sfn_id + ":state/SNS", "uses-service")
        if True:
            top.assert_relation(relations, sfn_id + ":state/SNS", sfn_id + ":state/SQS", "uses-service")
            top.assert_relation(relations, sfn_id + ":state/SQS", sfn_id + ":state/SQSSecondaryRegion", "uses-service")
        # parallel branch 3
        top.assert_relation(relations, sfn_id + ":state/ParallelRun", sfn_id + ":state/Lambda", "uses-service")
        if True:
            top.assert_relation(relations, sfn_id + ":state/Lambda", sfn_id + ":state/LambdaOldVersion", "uses-service")
            top.assert_relation(
                relations, sfn_id + ":state/LambdaOldVersion", sfn_id + ":state/DynamoDB", "uses-service"
            )

        top.assert_relation(relations, sfn_id + ":state/ParallelRun", sfn_id + ":state/FakeInput", "uses-service")
        # iterator
        top.assert_relation(relations, sfn_id + ":state/FakeInput", sfn_id + ":state/ApiMap", "uses-service")
        if True:
            top.assert_relation(relations, sfn_id + ":state/ApiMap", sfn_id + ":state/ApiGateway", "uses-service")
        # choice
        top.assert_relation(relations, sfn_id + ":state/ApiMap", sfn_id + ":state/FakeChoice", "uses-service")
        if True:
            top.assert_relation(relations, sfn_id + ":state/FakeChoice", sfn_id + ":state/Finish", "uses-service")
            top.assert_relation(relations, sfn_id + ":state/FakeChoice", sfn_id + ":state/Activity", "uses-service")
        # last
        top.assert_relation(relations, sfn_id + ":state/Activity", sfn_id + ":state/NoFinish", "uses-service")

        # 15 states

        top.assert_relation(relations, sfn_id + ":state/SNS", get_id("SnsTopic"), "uses-service")
        top.assert_relation(relations, sfn_id + ":state/SQS", get_id("SqsQueue"), "uses-service")
        top.assert_relation(
            relations,
            sfn_id + ":state/SQSSecondaryRegion",
            get_id("SqsQueue", stack="stackstate-main-account-secondary-region", region="us-east-1"),
            "uses-service",
        )
        top.assert_relation(relations, sfn_id + ":state/DynamoDB", get_id("DynamoDbTable"), "uses-service")
        # TODO ApiGatewayV2 not yet supported (SO RELATION LEFT ALERTER)
        # TODO also verify if this is OK to refer to the API stage here?
        self.assertIn("UNSUPPORTED_ARN-AWS::ApiGatewayV2::", get_id("ApiGatewayApi") + "/test")
        # top.assert_relation(relations, sfn_id + ':state/ApiGateway', get_id('ApiGatewayApi') + '/test')

        top.assert_relation(relations, sfn_id + ":state/Lambda", get_id("LambdaFunction"), "uses-service")
        top.assert_relation(relations, sfn_id + ":state/LambdaOldVersion", get_id("LambdaFunction"), "uses-service")
        top.assert_relation(relations, sfn_id + ":state/ECS", get_id("EcsTaskDefinition"), "uses-service")
        top.assert_relation(relations, sfn_id + ":state/ECS", get_id("EcsCluster"), "uses-service")
        top.assert_relation(relations, sfn_id + ":state/Activity", get_id("StepFunctionsActivity"), "uses-service")
        # TODO IAM not yet supported (SO RELATION LEFT ALERTER)
        self.assertIn("UNSUPPORTED_ARN-AWS::IAM::", get_id("StepFunctionsIamRole"))
        # top.assert_relation(relations, sfn_id, get_id('StepFunctionsIamRole'))

        # MyStateMachine01 components + relations
        my_state_machine_01 = 'arn:aws:states:eu-west-1:548105126730:stateMachine:MyStateMachine01'
        top.assert_component(components, my_state_machine_01, 'aws.stepfunction.statemachine')
        top.assert_component(components, my_state_machine_01 + ':state/SNS', 'aws.stepfunction.state')
        top.assert_component(components, my_state_machine_01 + ':state/SQS', 'aws.stepfunction.state')
        top.assert_component(components, my_state_machine_01 + ':state/SQSSecondaryRegion', 'aws.stepfunction.state')
        top.assert_relation(relations, my_state_machine_01, my_state_machine_01 + ':state/SNS', 'uses-service')
        top.assert_relation(relations, my_state_machine_01 + ':state/SNS', my_state_machine_01 + ':state/SQS',
                            'uses-service')
        top.assert_relation(relations, my_state_machine_01 + ':state/SQS',
                            my_state_machine_01 + ':state/SQSSecondaryRegion', 'uses-service')
        top.assert_relation(relations, my_state_machine_01,
                            'arn:aws:iam::548105126730:role/service-role/StepFunctions-MyStateMachine01-role-7191ec4f',
                            'uses-service')
        top.assert_relation(relations, my_state_machine_01 + ':state/SNS',
                            'arn:aws:sns:eu-west-1:548105126730:'
                            'stackstate-main-account-main-region-SnsTopic-1WPRYH16ZAL14',
                            'uses-service')
        top.assert_relation(relations, my_state_machine_01 + ':state/SQSSecondaryRegion',
                            'arn:aws:sqs:us-east-1:548105126730:' 
                            'stackstate-main-account-secondary-region-SqsQueue-TCLBC173C8R2',
                            'uses-service')

        self.assertEqual(len(topology[0]["relations"]), 32)
        top.assert_all_checked(components, relations, unchecked_relations=2)

    def test_process_stepfunction_branch_state(self):
        location = location_info("acct", "test")
        branches = [
            {
                "StartAt": "B1S1",
                "States": {
                    "B1S1": {"Next": "B1S2"},
                    "B1S2": {"Type": "Parallel", "Branches": [{"StartAt": "B3S1", "States": {"B3S1": {}}}]},
                },
            },
            {"StartAt": "B2S1", "States": {"B2S1": {"Next": "B2S2"}, "B2S2": {}}},
        ]
        expected_relations = [
            {"source_id": "brancharn", "target_id": "root:state/B1S1", "type": "uses-service", "data": {}},
            {"source_id": "brancharn", "target_id": "root:state/B2S1", "type": "uses-service", "data": {}},
            {"source_id": "root:state/B1S1", "target_id": "root:state/B1S2", "type": "uses-service", "data": {}},
            {"source_id": "root:state/B2S1", "target_id": "root:state/B2S2", "type": "uses-service", "data": {}},
            {"source_id": "root:state/B1S2", "target_id": "root:state/B3S1", "type": "uses-service", "data": {}},
        ]
        expected_components = [
            {"id": "root:state/B1S1", "type": "aws.stepfunction.state"},
            {"id": "root:state/B3S1", "type": "aws.stepfunction.state"},
            {"id": "root:state/B1S2", "type": "aws.stepfunction.state"},
            {"id": "root:state/B2S1", "type": "aws.stepfunction.state"},
            {"id": "root:state/B2S2", "type": "aws.stepfunction.state"},
        ]
        agent = AgentMock()
        collector = StepFunctionCollector(location, None, agent)
        collector.process_parallel_state("root", "brancharn", branches)
        self.assertEqual(len(agent.relations), len(expected_relations))
        for relation in expected_relations:
            self.assertIn(relation, agent.relations)
        for component in agent.components:
            del component["data"]
        self.assertEqual(len(agent.components), len(expected_components))
        for component in expected_components:
            self.assertIn(component, agent.components)

    def test_process_stepfunction_task_state(self):
        location = location_info("acct", "test")
        nameonly_prefix = "arn:AWS::Lambda::Function:"
        arn_prefix = "arn:aws:lambda:region:account:function:"
        partial_prefix = "123456789012:function:"
        lambda_refs = [
            # name only
            {"ref": "one", "expected": nameonly_prefix + "one"},
            {"ref": "one:alias", "expected": nameonly_prefix + "one:alias"},
            {"ref": "one:1", "expected": nameonly_prefix + "one"},
            {"ref": "one:$latest", "expected": nameonly_prefix + "one"},
            # arn
            {"ref": arn_prefix + "one", "expected": arn_prefix + "one"},
            {"ref": arn_prefix + "one:alias", "expected": arn_prefix + "one:alias"},
            {"ref": arn_prefix + "one:1", "expected": arn_prefix + "one"},
            {"ref": arn_prefix + "one:$latest", "expected": arn_prefix + "one"},
            # partial
            {"ref": partial_prefix + "one", "expected": nameonly_prefix + "one"},
            {"ref": partial_prefix + "one:alias", "expected": nameonly_prefix + "one:alias"},
            {"ref": partial_prefix + "one:1", "expected": nameonly_prefix + "one"},
            {"ref": partial_prefix + "one:$latest", "expected": nameonly_prefix + "one"},
        ]
        for lambda_ref in lambda_refs:
            agent = AgentMock()
            collector = StepFunctionCollector(location, None, agent)
            state = {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:",
                "Parameters": {"FunctionName": lambda_ref["ref"]},
            }
            collector.process_task_state("rootstate", state)
            self.assertEqual(agent.relations[0]["target_id"], lambda_ref["expected"], lambda_ref["ref"])
        wrong_refs = [
            # name only
            {"ref": "1:2:3:4:5:6:7:8:9"},
            {"ref": "1:2:3:4:5"},
            {"ref": "1:2:3:4:5:6"},
        ]
        for lambda_ref in wrong_refs:
            agent = AgentMock()
            collector = StepFunctionCollector(location, None, agent)
            state = {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:",
                "Parameters": {"FunctionName": lambda_ref["ref"]},
            }
            collector.process_task_state("rootstate", state)
            self.assertIn("Could not make lambda relation of " + lambda_ref["ref"], agent.warnings)
        direct_refs = [
            {"ref": arn_prefix + "one", "expected": arn_prefix + "one"},
            {"ref": arn_prefix + "one:alias", "expected": arn_prefix + "one:alias"},
            {"ref": arn_prefix + "one:1", "expected": arn_prefix + "one"},
            {"ref": arn_prefix + "one:$latest", "expected": arn_prefix + "one"},
        ]
        for direct_ref in direct_refs:
            agent = AgentMock()
            collector = StepFunctionCollector(location, None, agent)
            state = {"Type": "Task", "Resource": direct_ref["ref"]}
            collector.process_task_state("rootstate", state)
            self.assertEqual(agent.relations[0]["target_id"], direct_ref["expected"], direct_ref["ref"])
        res_prefix = "arn:aws:states:::states:startExecution"
        stepf_arn = "arn:aws:states:region:account:stateMachine:one"
        stepf_refs = [
            {"res": res_prefix, "expected": stepf_arn},
            {"res": res_prefix + ".sync", "expected": stepf_arn},
            {"res": res_prefix + ".sync:2", "expected": stepf_arn},
            {"res": res_prefix + ".waitForTaskToken", "expected": stepf_arn},
        ]
        for stepf_ref in stepf_refs:
            agent = AgentMock()
            collector = StepFunctionCollector(location, None, agent)
            state = {"Type": "Task", "Resource": stepf_ref["res"], "Parameters": {"StateMachineArn": stepf_arn}}
            collector.process_task_state("rootstate", state)
            self.assertEqual(agent.relations[0]["target_id"], stepf_ref["expected"], stepf_ref["res"])

    @set_not_authorized("list_state_machines")
    def test_process_stepfunction_access_list_state_machines(self):
        self.check.run()
        self.assertIn(
            "Role arn:aws:iam::548105126730:role/RoleName needs states:ListStateMachines"
            + " was encountered 1 time(s).",
            self.check.warnings,
        )
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        components = topology[0]["components"]
        counts = Counter([component["type"] for component in components])
        self.assertEqual(dict(counts), {"aws.stepfunction.activity": 1})

    @set_not_authorized("list_activities")
    def test_process_stepfunction_access_list_activities(self):
        self.check.run()
        self.assertIn(
            "Role arn:aws:iam::548105126730:role/RoleName needs states:ListActivities" + " was encountered 1 time(s).",
            self.check.warnings,
        )
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        components = topology[0]["components"]
        counts = Counter([component["type"] for component in components])
        self.assertEqual(dict(counts), {"aws.stepfunction.statemachine": 2, "aws.stepfunction.state": 18})

    @set_not_authorized("describe_state_machine")
    def test_process_stepfunction_access_describe_state_machine(self):
        self.check.run()
        self.assertIn(
            "Role arn:aws:iam::548105126730:role/RoleName needs states:DescribeStateMachine"
            + " was encountered 2 time(s).",
            self.check.warnings,
        )
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        components = topology[0]["components"]
        counts = Counter([component["type"] for component in components])
        self.assertEqual(dict(counts), {"aws.stepfunction.statemachine": 2, "aws.stepfunction.activity": 1})

    @set_not_authorized("list_tags_for_resource")
    def test_process_stepfunction_access_list_tags_for_resource(self):
        self.check.run()
        self.assertIn(
            "Role arn:aws:iam::548105126730:role/RoleName needs states:ListTagsForResource"
            + " was encountered 3 time(s).",
            self.check.warnings,
        )
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        components = topology[0]["components"]
        counts = Counter([component["type"] for component in components])
        self.assertEqual(
            dict(counts),
            {"aws.stepfunction.statemachine": 2, "aws.stepfunction.activity": 1, "aws.stepfunction.state": 18},
        )

    @set_cloudtrail_event("create_state_machine")
    def test_process_stepfunction_create_state_machine(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["id"], "arn:aws:states:eu-west-1:548105126730:stateMachine:MyStateMachine")

    @set_cloudtrail_event("delete_state_machine")
    def test_process_stepfunction_delete_state_machine(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(self.check.delete_ids), 1)
        self.assertEqual(self.check.delete_ids[0], "arn:aws:states:eu-west-1:548105126730:stateMachine:MyStateMachine")

    @set_cloudtrail_event("update_state_machine")
    def test_process_stepfunction_update_state_machine(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["id"], "arn:aws:states:eu-west-1:548105126730:stateMachine:MyStateMachine")

    @set_cloudtrail_event("create_activity")
    def test_process_stepfunction_create_activity(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["id"], "arn:aws:states:eu-west-1:548105126730:activity:Test")

    @set_cloudtrail_event("delete_activity")
    def test_process_stepfunction_delete_activity(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(self.check.delete_ids), 1)
        self.assertEqual(self.check.delete_ids[0], "arn:aws:states:eu-west-1:548105126730:activity:Test")

    @set_cloudtrail_event("tag_activity")
    def test_process_stepfunction_tag_activity(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["id"], "arn:aws:states:eu-west-1:548105126730:activity:TestActivity")

    @set_cloudtrail_event("untag_activity")
    def test_process_stepfunction_untag_activity(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["id"], "arn:aws:states:eu-west-1:548105126730:activity:TestActivity")

    @set_cloudtrail_event("tag_state_machine")
    def test_process_stepfunction_tag_state_machine(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["id"], "arn:aws:states:eu-west-1:548105126730:stateMachine:MyStateMachine")

    @set_cloudtrail_event("untag_state_machine")
    def test_process_stepfunction_untag_state_machine(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["id"], "arn:aws:states:eu-west-1:548105126730:stateMachine:MyStateMachine")
