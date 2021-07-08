from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event, set_filter


class TestFirehose(BaseApiTest):
    def get_api(self):
        return "firehose"

    def get_account_id(self):
        return "548105126730"

    def test_process_firehose(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        firehose_arn_prefix = "arn:aws:firehose:eu-west-1:548105126730:deliverystream/"

        top.assert_component(
            components,
            firehose_arn_prefix + "firehose_1",
            "aws.firehose.delivery-stream",
            checks={
                "Name": "firehose_1",
                "DeliveryStreamARN": firehose_arn_prefix + "firehose_1",
                "Tags.SomeKey": "SomeValue",
                "CW.Dimensions": [{"Key": "DeliveryStreamName", "Value": "firehose_1"}],
            },
        )
        top.assert_component(
            components,
            firehose_arn_prefix + "firehose_2",
            "aws.firehose.delivery-stream",
            checks={
                "Name": "firehose_2",
                "DeliveryStreamARN": firehose_arn_prefix + "firehose_2",
                "CW.Dimensions": [{"Key": "DeliveryStreamName", "Value": "firehose_2"}],
            },
        )

        top.assert_relation(
            relations,
            "arn:aws:kinesis:eu-west-1:548105126730:stream/stream_1",
            firehose_arn_prefix + "firehose_1",
            "uses-service",
        )
        top.assert_relation(
            relations, firehose_arn_prefix + "firehose_1", "arn:aws:s3:::firehose-bucket_1", "uses-service"
        )
        top.assert_relation(
            relations, firehose_arn_prefix + "firehose_2", "arn:aws:s3:::firehose-bucket_2", "uses-service"
        )

        top.assert_all_checked(components, relations)

    @set_filter("xxx")
    def test_process_firehosel_filter_all(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 0)

    @set_cloudtrail_event("create_stream")
    def test_process_firehose_create_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "firehose_1",
            topology[0]["components"][0]["data"]["DeliveryStreamName"],
        )

    @set_cloudtrail_event("delete_stream")
    def test_process_firehose_delete_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn("arn:aws:firehose:eu-west-1:548105126730:deliverystream/firehose_1", self.check.delete_ids)

    @set_cloudtrail_event("start_encryption")
    def test_process_firehose_start_encryption(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:firehose:eu-west-1:548105126730:deliverystream/firehose_1", topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event("stop_encryption")
    def test_process_firehose_stop_encryption(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:firehose:eu-west-1:548105126730:deliverystream/firehose_1", topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event("tag_stream")
    def test_process_firehose_tag_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:firehose:eu-west-1:548105126730:deliverystream/firehose_1", topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event("untag_stream")
    def test_process_firehose_untag_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:firehose:eu-west-1:548105126730:deliverystream/firehose_1", topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event("update_destination")
    def test_process_firehose_update_destination(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:firehose:eu-west-1:548105126730:deliverystream/firehose_1", topology[0]["components"][0]["id"]
        )
