from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestSns(BaseApiTest):

    def get_api(self):
        return "sns"

    def test_process_sns(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        base_target_id = "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-"

        self.assert_has_relation(
            relations,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-1",
            base_target_id + "TopicHandler-11EWA2GN9YNLL"
        )
        self.assert_has_relation(
            relations,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-2",
            base_target_id + "TopicHandler-21EWA2GN9YNLL"
        )
        self.assert_has_relation(
            relations,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-3",
            base_target_id + "TopicHandler-31EWA2GN9YNLL"
        )
        self.assert_has_relation(
            relations,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-3",
            base_target_id + "TopicHandler-41EWA2GN9YNLL"
        )
        self.assert_has_relation(
            relations,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-3",
            "arn:aws:sqs:eu-west-1:731070500579:STS_stackpack_test"
        )

        self.assert_has_component(
            components,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-1",
            "aws.sns",
            checks={
                "TopicArn": "arn:aws:sns:eu-west-1:731070500579:my-topic-1",
                "Name": "my-topic-1",
                "Tags.SnsTagKey": "SnsTagValue",
                "CW.Dimensions": [
                    {"Key": "TopicName", "Value": "my-topic-1"}
                ]
            }
        )
        self.assert_location_info(topology[0]["components"][0])
        self.assert_has_component(
            components,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-2",
            "aws.sns"
        )
        self.assert_has_component(
            components,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-3",
            "aws.sns"
        )
        self.assert_has_component(
            components,
            "arn:aws:sns:eu-west-1:731070500579:my-topic-4",
            "aws.sns"
        )
        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)

    @set_cloudtrail_event('sns_create_topic')
    def test_process_sns_create_topic(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:sns:eu-west-1:731070500579:my-topic-1',
            topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event('sns_delete_topic')
    def test_process_sns_delete_topic(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn(
            'arn:aws:sns:eu-west-1::my-topic-1', self.check.delete_ids)
