from stackstate_checks.base.stubs import topology as top, aggregator
from .conftest import BaseApiTest, set_cloudtrail_event


class TestElasticLoadbalancingV2(BaseApiTest):

    def get_api(self):
        return "elb"

    def test_process_elb(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        events = aggregator.events

        self.assertEqual(len(events), 2)  # TODO nothing is checked on the events
        top.assert_component(
            components,
            "classic_elb_classic-loadbalancer-1",
            "aws.elb_classic",
            {
                'LoadBalancerName': 'classic-loadbalancer-1',
                'Tags.stackstate-environment': 'Production',
                'URN': ["arn:aws:elasticloadbalancing:{}:123456789012:loadbalancer/{}".format(
                    "eu-west-1", "classic-loadbalancer-1"
                )]
            }
        )
        top.assert_relation(
            relations,
            "classic_elb_classic-loadbalancer-1",
            "vpc-6b25d10e",
            "uses service"
        )
        top.assert_relation(
            relations,
            "classic_elb_classic-loadbalancer-1",
            "sg-193aec7c",
            "uses service"
        )
        top.assert_relation(
            relations,
            "classic_elb_classic-loadbalancer-1",
            "i-09388d5bfc0ab9e78",
            "uses service"
        )
        top.assert_relation(
            relations,
            "classic_elb_classic-loadbalancer-1",
            "i-05b20853cc72c23c4",
            "uses service"
        )

        top.assert_all_checked(components, relations)

    @set_cloudtrail_event('create_loadbalancer')
    def test_process_elb_create_loadbalancer(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'classic_elb_classic-loadbalancer-1',
            topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event('delete_loadbalancer')
    def test_process_elb_delete_loadbalancer(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('classic_elb_classic-lb', self.check.delete_ids)

    @set_cloudtrail_event('register_instances_with_loadbalancer')
    def test_process_elb_register_instances_with_loadbalancer(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'classic_elb_classic-loadbalancer-1',
            topology[0]["components"][0]["id"]
        )
