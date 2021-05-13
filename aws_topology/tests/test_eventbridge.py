import unittest
import os
import json
from mock import patch
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
import hashlib
import botocore
from functools import reduce


def get_params_hash(data):
    return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode('utf-8')).hexdigest()[0:7]


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


class TestEvents(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

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
        file_name = "json/eventbridge/{}_{}.json".format(operation_name, get_params_hash(args))
        try:
            return resource(file_name) 
        except Exception:
            error = "API response file not found for operation: {}\n".format(operation_name)
            error += "Parameters:\n{}\n".format(json.dumps(args[1], indent=2, default=str))
            error += "File missing: {}".format(file_name)
            raise Exception(error)

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
            "role_arn": "arn:aws:iam::548105126730:role/RoleName",
            "regions": ["eu-west-1"],
        }
        instance.update({"apis_to_run": ["events"]})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        self.mock_object.side_effect = self.mock_boto_calls

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    def assert_has_component(self, components, id, tp, checks={}):
        comp = None
        for component in components:
            if component['id'] == id and component['type'] == tp:
                comp = component
                break
        self.assertIsNotNone(comp, "Component not found " + id + " - " + tp)
        for key in checks:
            self.assertEqual(reduce(dict.__getitem__, ('data.' + key).split('.'), comp), checks[key])
        return comp

    def assert_has_relation(self, relations, source_id, target_id):
        for relation in relations:
            if relation["source_id"] == source_id and relation["target_id"] == target_id:
                return relation
        self.assertTrue(False, "Relation expected source_id={} target_id={}".format(source_id, target_id))

    def test_process_events(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        def get_arn(resource_type, resource_id, api="events"):
            return "arn:aws:{}:eu-west-1:548105126730:{}/{}".format(
                api,
                resource_type,
                resource_id
            )
            
        # check default bus
        bus_name = "default"
        self.assert_has_component(
            components,
            get_arn("event-bus", bus_name),
            "aws.events.bus",
            checks={
                "Location.AwsAccount": "548105126730",
                "Location.AwsRegion": "eu-west-1",
                "Name": bus_name
            }
        )
        # bus is related to 2 rules
        # rule 1
        rule_name = "stackstate-main-account-main-r-EventBridgeCronRule-1ATSJ2IVLLTHS"
        self.assert_has_component(components, get_arn("rule", rule_name), "aws.events.rule")
        self.assert_has_relation(relations, get_arn("rule", rule_name), get_arn("event-bus", bus_name))
        # rule 1 has a target
        self.assert_has_component(components, "sqs", "aws.events.target")
        self.assert_has_relation(relations, get_arn("rule", rule_name), "sqs")
        # target has relation with a resource
        resource_id = "arn:aws:sqs:eu-west-1:548105126730:stackstate-main-account-main-region-SqsQueue-1CIRWAM6D60JD"
        self.assert_has_relation(relations, "sqs", resource_id)
        # rule 2
        rule_name = "stackstate-resources-debug-StsEc2Rule-SJBRONO1KVPN"
        self.assert_has_component(components, get_arn("rule", rule_name), "aws.events.rule")
        self.assert_has_relation(relations, get_arn("rule", rule_name), get_arn("event-bus", bus_name))
        # rule 2 has a target
        target_id = "StsEventBridgeFirehose"
        self.assert_has_component(components, target_id, "aws.events.target")
        self.assert_has_relation(relations, get_arn("rule", rule_name), target_id)
        # target has relation with resource and role
        resource_id = "arn:aws:firehose:eu-west-1:548105126730:deliverystream/stackstate-eventbridge-stream"
        role_id = "arn:aws:iam::548105126730:role/StackStateEventBridgeRole-eu-west-1"
        self.assert_has_relation(relations, target_id, resource_id)
        self.assert_has_relation(relations, target_id, role_id)
        # bus 2
        stack_name = "stackstate-main-account-main-region"
        bus_name = "stackstate-main-account-main-region"
        self.assert_has_component(
            components,
            get_arn("event-bus", bus_name),
            "aws.events.bus",
            checks={
                "Name": bus_name
            }
        )
        # bus 2 has 2 rules
        # rule 1
        rule_name = stack_name + "/Events-Archive-EventBridgeArchive-oLlo8WLrFl3H"
        self.assert_has_component(components, get_arn("rule", rule_name), "aws.events.rule")
        self.assert_has_relation(relations, get_arn("rule", rule_name), get_arn("event-bus", bus_name))
        # rule 1 has a target
        target_id = "Events-Archive-EventBridgeArchive-oLlo8WLrFl3H"
        self.assert_has_component(components, target_id, "aws.events.target")
        self.assert_has_relation(relations, get_arn("rule", rule_name), target_id)
        # target is related to a resource
        # TODO this is very strange target
        self.assert_has_relation(relations, target_id, "arn:aws:events:eu-west-1:::")
        # rule 2
        rule_name = stack_name + "/stackstate-main-account-m-EventBridgeCustomBusRule-1LDKRBE651N2B"
        self.assert_has_component(components, get_arn("rule", rule_name), "aws.events.rule")
        self.assert_has_relation(relations, get_arn("rule", rule_name), get_arn("event-bus", bus_name))
        # rule 2 has a target
        self.assert_has_component(components, "schedule", "aws.events.target")
        self.assert_has_relation(relations, get_arn("rule", rule_name), "schedule")
        # target has relation with 2 resources
        resource_id = "arn:aws:states:eu-west-1:548105126730:stateMachine:StepFunctionsStateMachine-wAXvzDJDy4ja"
        role_id = "arn:aws:iam::548105126730:role/stackstate-main-account-main-re-EventBridgeIamRole-IW90IMP0QROZ"
        self.assert_has_relation(relations, "schedule", resource_id)
        self.assert_has_relation(relations, "schedule", role_id)
        # bus 2 has an archive
        archive_id = "arn:aws:events:eu-west-1:548105126730:archive/EventBridgeArchive-oLlo8WLrFl3H"
        self.assert_has_component(
            components,
            archive_id,
            "aws.events.archive"
        )
        self.assert_has_relation(relations, archive_id, get_arn("event-bus", bus_name))