import unittest
import os
import json
from mock import patch
import datetime
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


def set_event(value):
    def inner(func):
        func.event = value
        return func

    return inner


def mock_event(event_name):

    def mock_boto_calls(operation_name, kwarg=None):
        if operation_name == "AssumeRole":
            return {"Credentials": {"AccessKeyId": "KEY_ID", "SecretAccessKey": "ACCESS_KEY", "SessionToken": "TOKEN"}}
        elif operation_name == 'LookupEvents':
            res = resource("json/cloudtrail/" + event_name + ".json")
            res['eventTime'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            msg = {
                "Events": [
                    {
                        "CloudTrailEvent": json.dumps(res)
                    }
                ]
            }
            return msg
        elif operation_name == 'GetQueueAttributes':
            return resource("json/cloudtrail/get_queue_attributes.json")
        elif operation_name == 'ListQueueTags':
            return {}
        raise ValueError("Unknown operation name", operation_name)

    return mock_boto_calls


class TestCloudtrail(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        method = getattr(self, self._testMethodName)
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
        instance.update({"apis_to_run": []})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        self.mock_object.side_effect = mock_event(method.event)

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    @set_event('sqs_create_queue')
    def test_process_sqs_create(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'https://sqs.eu-west-1.amazonaws.com/123456789012/CreatedQueueName',
            topology[0]["components"][0]["data"]["QueueUrl"]
        )

    @set_event('sqs_set_queue_attributes')
    def test_process_sqs_update_attributes(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'https://sqs.eu-west-1.amazonaws.com/123456789012/UpdatedQueue',
            topology[0]["components"][0]["data"]["QueueUrl"]
        )

    @set_event('sqs_tag_queue')
    def test_process_sqs_tag_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'https://sqs.eu-west-1.amazonaws.com/123456789012/TaggedQueue',
            topology[0]["components"][0]["data"]["QueueUrl"]
        )

    @set_event('sqs_untag_queue')
    def test_process_sqs_untag_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'https://sqs.eu-west-1.amazonaws.com/123456789012/UntaggedQueue',
            topology[0]["components"][0]["data"]["QueueUrl"]
        )

    @set_event('sqs_delete_queue')
    def test_process_sqs_delete_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('https://sqs.eu-west-1.amazonaws.com/123456789012/DeletedQueue', self.check.delete_ids)

    @set_event('sqs_purge_queue')
    def test_process_sqs_purge_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertEqual(len(self.check.delete_ids), 0)
