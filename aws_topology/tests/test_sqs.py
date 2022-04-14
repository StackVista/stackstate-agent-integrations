from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event
from stackstate_checks.aws_topology.resources.sqs import create_arn


class TestSqs(BaseApiTest):
    def get_api(self):
        return "sqs"

    def get_account_id(self):
        return "731070500579"

    def test_process_sqs(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        component = top.assert_component(
            components,
            "arn:aws:sqs:eu-west-1:731070500579:STS_stackpack_test",
            "aws.sqs.queue",
            checks={
                "Tags.a": "b",
                "Name": "STS_stackpack_test",
                "URN": ["https://sqs.eu-west-1.amazonaws.com/731070500579/STS_stackpack_test"],
                "CW.Dimensions": [{"Key": "QueueName", "Value": "STS_stackpack_test"}],
            },
        )
        self.assert_location_info(component)

        top.assert_all_checked(components, relations)

    def test_process_sqs_create_arn(self):
        with self.assertRaises(ValueError):
            create_arn(resource_id="test")
        self.assertEqual(
            create_arn(resource_id="https://sqs.eu-west-1.amazonaws.com/123456789012/myfirstqueue"),
            "arn:aws:sqs:eu-west-1:123456789012:myfirstqueue",
        )

    @set_cloudtrail_event("sqs_create_queue")
    def test_process_sqs_create(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "https://sqs.eu-west-1.amazonaws.com/731070500579/STS_stackpack_test",
            topology[0]["components"][0]["data"]["QueueUrl"],
        )

    @set_cloudtrail_event("sqs_set_queue_attributes")
    def test_process_sqs_update_attributes(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "https://sqs.eu-west-1.amazonaws.com/731070500579/STS_stackpack_test",
            topology[0]["components"][0]["data"]["QueueUrl"],
        )

    @set_cloudtrail_event("sqs_tag_queue")
    def test_process_sqs_tag_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "https://sqs.eu-west-1.amazonaws.com/731070500579/STS_stackpack_test",
            topology[0]["components"][0]["data"]["QueueUrl"],
        )

    @set_cloudtrail_event("sqs_untag_queue")
    def test_process_sqs_untag_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "https://sqs.eu-west-1.amazonaws.com/731070500579/STS_stackpack_test",
            topology[0]["components"][0]["data"]["QueueUrl"],
        )

    @set_cloudtrail_event("sqs_delete_queue")
    def test_process_sqs_delete_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn("arn:aws:sqs:eu-west-1:731070500579:DeletedQueue", self.check.delete_ids)
        topology = top.get_snapshot(self.check.check_id)
        assert topology["delete_ids"] == ["arn:aws:sqs:eu-west-1:731070500579:DeletedQueue"]

    @set_cloudtrail_event("sqs_purge_queue")
    def test_process_sqs_purge_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertEqual(len(self.check.delete_ids), 0)
        # TODO test that an event is emitted
