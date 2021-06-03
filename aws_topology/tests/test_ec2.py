from stackstate_checks.aws_topology.resources.utils import deep_sort_lists
from stackstate_checks.base.stubs import topology as top, aggregator
from .conftest import BaseApiTest, set_cloudtrail_event, set_filter, use_subdirectory


class TestEC2(BaseApiTest):

    def get_api(self):
        return "ec2"

    def get_account_id(self):
        return "731070500579"
    
    def get_region(self):
        return 'eu-west-1'

    @set_filter('instances')
    def test_process_ec2_instances(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        test_instance_id = "i-0aac5bab082561475"
        test_instance_type = "m4.xlarge"
        test_public_ip = "172.30.0.96"
        test_public_dns = "ec2-172-30-0-96.eu-west-1.compute.amazonaws.com"

        events = aggregator.events

        self.assert_has_component(
            components,
            test_instance_id,
            "aws.ec2",
            checks={
                'InstanceId': test_instance_id,
                'InstanceType': test_instance_type,
                'Tags': {
                    'Name': "Martijn's Stackstate",
                    'host': test_instance_id,
                    'instance-id': test_instance_id,
                    'private-ip': test_public_ip,
                    'fqdn': test_public_dns,
                    'public-ip': test_public_ip
                },
                'URN': [
                    "urn:host:/{}".format(test_instance_id),
                    "arn:aws:ec2:{}:731070500579:instance/{}".format('eu-west-1', test_instance_id),
                    "urn:host:/{}".format(test_public_dns),
                    "urn:host:/{}".format(test_public_ip)
                ]
            }
        )

        self.assert_has_relation(
            relations,
            test_instance_id,
            "subnet-67d82910"
        )
        self.assert_has_relation(
            relations,
            test_instance_id,
            "sg-41c3cc3b"
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["host"], test_instance_id)
        self.assertEqual(events[0]["tags"], ["state:stopped"])

        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)

    first_security_group_version = "56b81fa0a7cb32a2d5be815f1fb4130764f19e8ab734cec3824854d7a5a9fa84"
    first_sg_group_id = "sg-002abe0b505ad7002"

    @set_filter('security_groups')
    def test_process_ec2_security_groups(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 49)
        self.assertEqual(len(topology[0]["relations"]), 49)

        self.assert_has_component(
            components,
            self.first_sg_group_id,
            "aws.security-group",
            checks={
                "URN": [
                    "arn:aws:ec2:{}:731070500579:security-group/{}".format('eu-west-1', self.first_sg_group_id)
                ],
                "Version": self.first_security_group_version,
                "Name": "network-ALBSecurityGroupPublic-1DNVWX102724V"
            }
        )


    @set_filter('security_groups')
    @use_subdirectory('alternate')
    def test_process_ec2_security_groups_order_has_no_influence_on_hash(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        self.assert_has_component(
            components,
            self.first_sg_group_id,
            "aws.security-group",
            checks={
                "URN": [
                    "arn:aws:ec2:{}:731070500579:security-group/{}".format('eu-west-1', self.first_sg_group_id)
                ],
                "Version": self.first_security_group_version,
                "Name": "network-ALBSecurityGroupPublic-1DNVWX102724V"
            }
        )

    @set_filter('vpcs')
    def test_process_ec2_vpcs(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        self.assertEqual(topology[0]["components"][0]["id"], "vpc-6b25d10e")  # DIFF
        self.assertEqual(topology[0]["components"][0]["type"], "aws.vpc")  # DIFF
        self.assertEqual(topology[0]["components"][0]["data"]["VpcId"], "vpc-6b25d10e")
        self.assertEqual(topology[0]["components"][0]["data"]["Name"], "vpc-6b25d10e")
        self.assertEqual(
            topology[0]["components"][0]["data"]["URN"],
            ["arn:aws:ec2:{}:731070500579:vpc/{}".format('eu-west-1', "vpc-6b25d10e")],
        )
        self.assert_location_info(topology[0]["components"][0])
        self.assertEqual(topology[0]["components"][1]["id"], "subnet-9e4be5f9")  # DIFF
        self.assertEqual(topology[0]["components"][1]["type"], "aws.subnet")  # DIFF
        self.assertEqual(topology[0]["components"][1]["data"]["SubnetId"], "subnet-9e4be5f9")
        self.assertEqual(topology[0]["components"][1]["data"]["Tags"], {"Name": "demo-deployments"})
        self.assertEqual(
            topology[0]["components"][1]["data"]["URN"],
            ["arn:aws:ec2:{}:731070500579:subnet/{}".format('eu-west-1', "subnet-9e4be5f9")],
        )
        self.assertEqual(topology[0]["components"][1]["data"]["Name"], "demo-deployments-eu-west-1a")
        self.assert_location_info(topology[0]["components"][1])
        self.assertEqual(len(topology[0]["relations"]), 1)
        self.assertEqual(topology[0]["relations"][0]["source_id"], "subnet-9e4be5f9")  # DIFF
        self.assertEqual(topology[0]["relations"][0]["target_id"], "vpc-6b25d10e")  # DIFF

    @set_filter('vpn_gateways')
    def test_process_ec2_vpn_gateways(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        self.assertEqual(topology[0]["components"][0]["id"], "vgw-b8c2fccc")  # DIFF
        self.assertEqual(topology[0]["components"][0]["data"]["VpnGatewayId"], "vgw-b8c2fccc")
        self.assertEqual(topology[0]["components"][0]["type"], "aws.vpngateway")  # DIFF
        self.assert_location_info(topology[0]["components"][0])
        self.assertEqual(len(topology[0]["relations"]), 1)
        self.assertEqual(topology[0]["relations"][0]["source_id"], "vgw-b8c2fccc")  # DIFF
        self.assertEqual(topology[0]["relations"][0]["target_id"], "vpc-6b25d10e")  # DIFF


    @set_cloudtrail_event('run_instances')
    def test_process_ec2_run_instances(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'i-0f70dba7ea83d6dec',
            topology[0]["components"][0]["id"]
        )
