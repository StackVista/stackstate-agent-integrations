from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestKinesis(BaseApiTest):

    def get_api(self):
        return "kinesis"

    def get_account_id(self):
        return "731070500579"
    
    def get_region(self):
        return 'eu-west-1'

    def test_process_kinesis(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        base_stream_arn = "arn:aws:kinesis:eu-west-1:731070500579:stream/"

        self.assert_has_component(
            components,
            base_stream_arn + "stream_1",
            "aws.kinesis",
            checks={
                "Name": "stream_1",
                "StreamDescriptionSummary.StreamARN": "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1"
            }
        )
        self.assert_has_component(
            components,
            base_stream_arn + "stream_2",
            "aws.kinesis",
            checks={
                "Name": "stream_2"
            }
        )
        self.assert_has_component(
            components,
            base_stream_arn + "stream_3",
            "aws.kinesis",
            checks={
                "Name": "stream_3"
            }
        )
        self.assert_has_component(
            components,
            base_stream_arn + "stream_4",
            "aws.kinesis",
            checks={
                "Name": "stream_4"
            }
        )

        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)
