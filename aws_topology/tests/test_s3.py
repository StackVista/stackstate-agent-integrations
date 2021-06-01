from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestS3(BaseApiTest):

    def get_api(self):
        return "s3"

    def get_account_id(self):
        return "548105126730"

    def test_process_s3(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        target_id = (
            "arn:aws:lambda:eu-west-1:731070500579:"
            + "function:com-stackstate-prod-s-NotifyBucketEventsHandle-1W0B5NSZYJ3G1"
        )

        self.assert_has_component(
            components,
            "arn:aws:s3:::stackstate.com",
            "aws.s3_bucket",
            checks={
                "Name": "stackstate.com",
                "Tags.BucketTag": "TagValue",
                "BucketLocation": "eu-west-1"
            }
        )
        self.assert_location_info(topology[0]["components"][0])

        self.assert_has_component(
            components,
            "arn:aws:s3:::binx.io",
            "aws.s3_bucket",
            checks={
                "Name": "binx.io"
            }
        )

        self.assert_has_relation(
            relations,
            "arn:aws:s3:::stackstate.com",
            target_id,
            type="uses service",
            checks={
                "event_type": "s3:ObjectCreated:*"
            }
        )
        self.assert_has_relation(
            relations,
            "arn:aws:s3:::binx.io",
            target_id,
            type="uses service",
            checks={
                "event_type": "s3:ObjectRemoved:*"
            }
        )

        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)

    @set_cloudtrail_event('create_bucket')
    def test_process_s3_create_bucket(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stackstate.com',
            topology[0]["components"][0]["data"]["Name"]
        )

    @set_cloudtrail_event('delete_bucket')
    def test_process_s3_delete_bucket(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:s3:::binx.io', self.check.delete_ids)
