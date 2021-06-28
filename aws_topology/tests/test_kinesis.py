from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestKinesis(BaseApiTest):
    def get_api(self):
        return "kinesis"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return "eu-west-1"

    def test_process_kinesis(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        base_stream_arn = "arn:aws:kinesis:eu-west-1:731070500579:stream/"

        top.assert_component(
            components,
            base_stream_arn + "stream_1",
            "aws.kinesis.data-stream",
            checks={
                "Name": "stream_1",
                "StreamDescriptionSummary.StreamARN": "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1",
                "Tags.TestKey": "TestValue",
            },
        )
        top.assert_component(components, base_stream_arn + "stream_2", "aws.kinesis.data-stream", checks={"Name": "stream_2"})
        top.assert_component(components, base_stream_arn + "stream_3", "aws.kinesis.data-stream", checks={"Name": "stream_3"})
        top.assert_component(components, base_stream_arn + "stream_4", "aws.kinesis.data-stream", checks={"Name": "stream_4"})

        top.assert_all_checked(components, relations)

    @set_cloudtrail_event("create_stream")
    def test_process_kinesis_create_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("delete_stream")
    def test_process_kinesis_delete_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn("arn:aws:kinesis:eu-west-1:731070500579:stream/TestStream", self.check.delete_ids)

    @set_cloudtrail_event("tag_stream")
    def test_process_kinesis_tag_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("untag_stream")
    def test_process_kinesis_untag_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("increase_retention")
    def test_process_kinesis_increase_retention(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("decrease_retention")
    def test_process_kinesis_decrease_retention(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("enable_enh_monitoring")
    def test_process_kinesis_enable_enh_monitoring(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("disable_enh_monitoring")
    def test_process_kinesis_disable_enh_monitoring(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("start_encryption")
    def test_process_kinesis_start_encryption(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("stop_encryption")
    def test_process_kinesis_stop_encryption(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])

    @set_cloudtrail_event("update_shard_count")
    def test_process_kinesis_update_shard_count(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("stream_1", topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"])
