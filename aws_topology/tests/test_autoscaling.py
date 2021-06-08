from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestAutoScaling(BaseApiTest):

    def get_api(self):
        return "autoscaling"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return 'eu-west-1'

    def test_process_autoscaling(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        # TODO this needs to be fixed in go, delete_ids need to be passed
        topology[0]["delete_ids"] = self.check.delete_ids

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        group_arn = "arn:aws:autoscaling:eu-west-1:731070500579:" \
            + "autoScalingGroup:e1155c2b-016a-40ad-8cba-2423c349574b:" \
            + "autoScalingGroupName/awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM"

        comp = top.assert_component(
            components,
            "awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM",
            "aws.autoscaling",
            checks={
                "AutoScalingGroupARN": group_arn
            }
        )
        self.assert_location_info(comp)

        top.assert_relation(
            relations,
            "classic_elb_awseb-e-g-AWSEBLoa-1WTFTHM4EDGUX",
            group_arn,
            "uses service"
        )
        top.assert_relation(
            relations,
            group_arn,
            "i-063c119ff97e71b82",
            "uses service"
        )
        top.assert_relation(
            relations,
            group_arn,
            "i-0928b13f776ba8e76",
            "uses service"
        )
        top.assert_relation(
            relations,
            group_arn,
            "i-0ed02eb3eab5399fb",
            "uses service"
        )

        self.assertEqual(len(topology[0]["delete_ids"]), 3)

        top.assert_all_checked(components, relations)

    @set_cloudtrail_event('create_autoscaling_group')
    def test_process_autoscaling_create_autoscaling_group(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM',
            topology[0]["components"][0]["data"]["AutoScalingGroupName"]
        )

    @set_cloudtrail_event('delete_autoscaling_group')
    def test_process_autoscaling_delete_autoscaling_group(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn(
            'elvin-stackstate-tests-main-account-main-region-EcsAutoScalingGroup-VVC5WIJ3AI3K',
            self.check.delete_ids
        )

    @set_cloudtrail_event('create_or_update_tags')
    def test_process_autoscaling_create_or_update_tags(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM',
            topology[0]["components"][0]["data"]["AutoScalingGroupName"]
        )

    @set_cloudtrail_event('update_autoscaling_group')
    def test_process_autoscaling_update_autoscaling_group(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM',
            topology[0]["components"][0]["data"]["AutoScalingGroupName"]
        )
