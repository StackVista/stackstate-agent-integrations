from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestElasticLoadbalancingV2(BaseApiTest):
    def get_api(self):
        return "elbv2"

    def test_process_elbv2(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        instance_a = "i-0a7182087df63a90b"
        instance_b = "i-0d857740370079c95"

        prefix = "arn:aws:elasticloadbalancing:eu-west-1:731070500579:"

        # LoadBalancer
        top.assert_component(
            components, prefix + "loadbalancer/app/myfirstloadbalancer/90dd512583d2d7e9", "aws.elb_v2_application"
        )
        # TargetGroup
        top.assert_component(
            components, prefix + "targetgroup/myfirsttargetgroup/28ddec997ec55d21", "aws.elb_v2_target_group"
        )
        # ELB Target Group Instance A
        top.assert_component(
            components, "urn:aws/target-group-instance/" + instance_a, "aws.elb_v2_target_group_instance"
        )
        # ELB Target Group Instance B
        top.assert_component(
            components, "urn:aws/target-group-instance/" + instance_b, "aws.elb_v2_target_group_instance"
        )

        # LoadBalancer <-> TargetGroup
        top.assert_relation(
            relations,
            prefix + "loadbalancer/app/myfirstloadbalancer/90dd512583d2d7e9",
            prefix + "targetgroup/myfirsttargetgroup/28ddec997ec55d21",
            "uses service",
        )
        # Load Balancer A and Target Group A relationship test
        top.assert_relation(
            relations,
            prefix + "targetgroup/myfirsttargetgroup/28ddec997ec55d21",
            "urn:aws/target-group-instance/" + instance_a,
            "uses service",
        )
        # Load Balancer B and Target Group B relationship test
        top.assert_relation(
            relations,
            prefix + "targetgroup/myfirsttargetgroup/28ddec997ec55d21",
            "urn:aws/target-group-instance/" + instance_b,
            "uses service",
        )
        # LoadBalancer <-> SecurityGroup
        top.assert_relation(
            relations, prefix + "loadbalancer/app/myfirstloadbalancer/90dd512583d2d7e9", "sg-193aec7c", "uses service"
        )
        # LoadBalancer <-> Vpc
        top.assert_relation(
            relations, prefix + "loadbalancer/app/myfirstloadbalancer/90dd512583d2d7e9", "vpc-6b25d10e", "uses service"
        )
        # TargetGroup <-> Vpc
        top.assert_relation(
            relations, prefix + "targetgroup/myfirsttargetgroup/28ddec997ec55d21", "vpc-6b25d10e", "uses service"
        )

        top.assert_all_checked(components, relations)

    @set_cloudtrail_event("create_loadbalancer")
    def test_process_elbv2_create_loadbalancer(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:elasticloadbalancing:eu-west-1:123456789012:"
            + "loadbalancer/app/elvin-s-Alb-14EDDDCB8Z0I7/0865db53d9ea539c",
            topology[0]["components"][0]["id"],
        )

    @set_cloudtrail_event("delete_loadbalancer")
    def test_process_elbv2_delete_loadbalancer(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn(
            "arn:aws:elasticloadbalancing:eu-west-1:123456789012:"
            + "loadbalancer/app/elvin-s-Alb-4F9VFHSI01HZ/ff7597e671b574e2",
            self.check.delete_ids,
        )

    @set_cloudtrail_event("create_target_group")
    def test_process_elbv2_create_target_group(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 3)

        components = topology[0]["components"]
        top.assert_component(
            components,
            "arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/"
            + "elvin-AlbEc-PYQ8ZCZDRD5E/6e2b19e842496efb",
            "aws.elb_v2_target_group",
        )

    @set_cloudtrail_event("delete_target_group")
    def test_process_elbv2_delete_target_group(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn(
            "arn:aws:elasticloadbalancing:eu-west-1:123456789012:"
            + "targetgroup/elvin-AlbEc-R1C7CFXLU55G/9d1d0bad619ddb8c",
            self.check.delete_ids,
        )

    # TODO AccessDenied resilience tests
    # TODO Transformation failure tests
