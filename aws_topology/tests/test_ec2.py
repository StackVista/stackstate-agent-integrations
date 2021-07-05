from stackstate_checks.base.stubs import topology as top, aggregator
from .conftest import BaseApiTest, set_cloudtrail_event, set_eventbridge_event, set_filter, use_subdirectory
import sys
from mock import patch


class TestEC2(BaseApiTest):
    def get_api(self):
        return "ec2"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return "eu-west-1"

    @set_filter("instances")
    def test_process_ec2_instances(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        test_instance_id = "i-0f70dba7ea83d6dec"
        test_instance_type = "m4.xlarge"
        test_public_ip = "172.30.0.96"
        test_public_dns = "ec2-172-30-0-96.eu-west-1.compute.amazonaws.com"

        events = aggregator.events

        top.assert_component(
            components,
            test_instance_id,
            "aws.ec2.instance",
            checks={
                "InstanceId": test_instance_id,
                "InstanceType": test_instance_type,
                "IsNitro": False,
                "Tags": {
                    "Name": "Martijn's Stackstate",
                    "host": test_instance_id,
                    "instance-id": test_instance_id,
                    "private-ip": test_public_ip,
                    "fqdn": test_public_dns,
                    "public-ip": test_public_ip,
                },
                "URN": [
                    "urn:host:/{}".format(test_instance_id),
                    "arn:aws:ec2:{}:731070500579:instance/{}".format("eu-west-1", test_instance_id),
                    "urn:host:/{}".format(test_public_dns),
                    "urn:host:/{}".format(test_public_ip),
                ],
            },
        )

        top.assert_relation(relations, test_instance_id, "subnet-67d82910", "uses service")
        top.assert_relation(relations, test_instance_id, "sg-41c3cc3b", "uses service")

        # nitro instances
        top.assert_component(
            components,
            "i-1234567890123456",
            "aws.ec2.instance",
            checks={"InstanceId": "i-1234567890123456", "InstanceType": "m6gd.medium", "IsNitro": True},
        )
        top.assert_relation(relations, "i-1234567890123456", "vpc-6b25d10e", "uses service")
        top.assert_relation(relations, "i-1234567890123456", "sg-41c3cc3b", "uses service")

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["host"], test_instance_id)
        self.assertEqual(events[0]["tags"], ["state:stopped"])
        self.assertEqual(events[1]["host"], "i-1234567890123456")
        self.assertEqual(events[1]["tags"], ["state:running"])

        top.assert_all_checked(components, relations)

    first_security_group_version_py3 = "56b81fa0a7cb32a2d5be815f1fb4130764f19e8ab734cec3824854d7a5a9fa84"
    first_security_group_version_py2 = "e3a3e4764fd7fd4a51fcd5812ce9a4803a412c28c6830678462301d33ce6ce75"
    first_sg_group_id = "sg-002abe0b505ad7002"

    @set_filter("security_groups")
    def test_process_ec2_security_groups(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        self.assertEqual(len(components), 49)
        self.assertEqual(len(relations), 49)

        if sys.version_info.major == 3:
            version_to_check = self.first_security_group_version_py3
        else:
            version_to_check = self.first_security_group_version_py2

        top.assert_component(
            components,
            self.first_sg_group_id,
            "aws.ec2.security-group",
            checks={
                "URN": ["arn:aws:ec2:{}:731070500579:security-group/{}".format("eu-west-1", self.first_sg_group_id)],
                "Version": version_to_check,
                "Name": "network-ALBSecurityGroupPublic-1DNVWX102724V",
            },
        )

        top.assert_all_checked(components, relations, unchecked_components=48, unchecked_relations=49)

    @set_filter("security_groups")
    @use_subdirectory("alternate")
    def test_process_ec2_security_groups_order_has_no_influence_on_hash(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        if sys.version_info.major == 3:
            version_to_check = self.first_security_group_version_py3
        else:
            version_to_check = self.first_security_group_version_py2

        top.assert_component(
            components,
            self.first_sg_group_id,
            "aws.ec2.security-group",
            checks={
                "URN": ["arn:aws:ec2:{}:731070500579:security-group/{}".format("eu-west-1", self.first_sg_group_id)],
                "Version": version_to_check,
                "Name": "network-ALBSecurityGroupPublic-1DNVWX102724V",
            },
        )

        top.assert_all_checked(components, relations, unchecked_components=48, unchecked_relations=49)

    @set_filter("vpcs")
    def test_process_ec2_vpcs(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        comp = top.assert_component(
            components,
            "vpc-6b25d10e",
            "aws.ec2.vpc",
            checks={
                "VpcId": "vpc-6b25d10e",
                "Name": "vpc-6b25d10e",
                "URN": ["arn:aws:ec2:{}:731070500579:vpc/{}".format("eu-west-1", "vpc-6b25d10e")],
            },
        )
        self.assert_location_info(comp)
        comp = top.assert_component(
            components,
            "vpc-12345678",
            "aws.ec2.vpc",
            checks={
                "VpcId": "vpc-12345678",
                "Name": "default",
            },
        )
        comp = top.assert_component(
            components,
            "vpc-87654321",
            "aws.ec2.vpc",
            checks={
                "VpcId": "vpc-87654321",
                "Name": "MyVpc",
            },
        )

        top.assert_all_checked(components, relations)

    @set_filter("subnets")
    def test_process_ec2_subnets(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        comp = top.assert_component(
            components,
            "subnet-9e4be5f9",
            "aws.ec2.subnet",
            checks={
                "SubnetId": "subnet-9e4be5f9",
                "Tags.Name": "demo-deployments",
                "URN": ["arn:aws:ec2:{}:731070500579:subnet/{}".format("eu-west-1", "subnet-9e4be5f9")],
                "Name": "demo-deployments-eu-west-1a",
            },
        )
        self.assert_location_info(comp)
        comp = top.assert_component(
            components,
            "subnet-12345678",
            "aws.ec2.subnet",
            checks={"SubnetId": "subnet-12345678", "Name": "subnet-12345678-eu-west-1a"},
        )

        top.assert_relation(relations, "subnet-9e4be5f9", "vpc-6b25d10e", "uses service")
        top.assert_relation(relations, "subnet-12345678", "vpc-6b25d10e", "uses service")

        top.assert_all_checked(components, relations)

    @set_filter("vpn_gateways")
    def test_process_ec2_vpn_gateways(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        comp = top.assert_component(
            components,
            "vgw-b8c2fccc",
            "aws.ec2.vpn-gateway",
            checks={
                "VpnGatewayId": "vgw-b8c2fccc",
            },
        )
        self.assert_location_info(comp)
        top.assert_relation(relations, "vgw-b8c2fccc", "vpc-6b25d10e", "uses service")

        top.assert_all_checked(components, relations)

    @set_cloudtrail_event("run_instances")
    def test_process_ec2_run_instances(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(components), 1)
        top.assert_component(
            components,
            "i-0f70dba7ea83d6dec",
            "aws.ec2.instance",
            checks={"InstanceId": "i-0f70dba7ea83d6dec", "LaunchTime": "2018-04-16T08:01:08+00:00"},
        )

    @set_cloudtrail_event("modify_instance_attribute")
    def test_process_ec2_modify_instance_attributes(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(topology[0]["components"]), 1)
        top.assert_component(
            components,
            "i-1234567890123456",
            "aws.ec2.instance",
            checks={"InstanceId": "i-1234567890123456", "InstanceType": "m6gd.medium"},
        )

    @set_cloudtrail_event("attach_volume")
    def test_process_ec2_attach_volume(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(topology[0]["components"]), 1)
        top.assert_component(
            components,
            "i-1234567890123456",
            "aws.ec2.instance",
            checks={
                "InstanceId": "i-1234567890123456",
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/sda1",
                        "Ebs": {
                            "Status": "attached",
                            "DeleteOnTermination": True,
                            "VolumeId": "vol-0b83c17b2c8bd35b2",
                            "AttachTime": "2018-04-05T09:34:07+00:00",
                        },
                    }
                ],
            },
        )

    @set_cloudtrail_event("detach_volume")
    def test_process_ec2_detach_volume(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(topology[0]["components"]), 1)
        top.assert_component(
            components,
            "i-1234567890123456",
            "aws.ec2.instance",
            checks={
                "InstanceId": "i-1234567890123456",
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/sda1",
                        "Ebs": {
                            "Status": "attached",
                            "DeleteOnTermination": True,
                            "VolumeId": "vol-0b83c17b2c8bd35b2",
                            "AttachTime": "2018-04-05T09:34:07+00:00",
                        },
                    }
                ],
            },
        )

    @set_cloudtrail_event("start_instances")
    def test_process_ec2_start_instances(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(topology[0]["components"]), 1)
        top.assert_component(
            components,
            "i-1234567890123456",
            "aws.ec2.instance",
            checks={"InstanceId": "i-1234567890123456", "State": {"Code": 16, "Name": "running"}},
        )

    @set_cloudtrail_event("stop_instances")
    def test_process_ec2_stop_instances(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(topology[0]["components"]), 1)
        top.assert_component(
            components,
            "i-0f70dba7ea83d6dec",
            "aws.ec2.instance",
            checks={"InstanceId": "i-0f70dba7ea83d6dec", "State": {"Code": 80, "Name": "stopped"}},
        )

    @set_cloudtrail_event("terminate_instances")
    def test_process_ec2_terminate_instances(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        components = topology[0]["components"]
        self.assertEqual(len(topology[0]["components"]), 1)
        top.assert_component(
            components,
            "i-0f70dba7ea83d6dec",
            "aws.ec2.instance",
            checks={
                "InstanceId": "i-0f70dba7ea83d6dec",
                "StateTransitionReason": "User initiated (2018-04-16 19:07:25 GMT)",
            },
        )

    @set_filter("xxx")
    @set_eventbridge_event("state_stopped")
    def test_process_ec2_state_stopped(self):
        with patch("stackstate_checks.aws_topology.AwsTopologyCheck.must_run_full", return_value=False):
            self.check.run()
            self.assert_updated_ok()
            events = aggregator.events
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "ec2_state")
            self.assertEqual(events[0]["host"], "i-0f70dba7ea83d6dec")
            self.assertEqual(events[0]["msg_text"], "stopped")
            self.assertEqual(events[0]["msg_title"], "EC2 instance state")
            self.assertEqual(events[0]["msg_text"], "stopped")
            self.assertEqual(events[0]["tags"], ["state:stopped"])

    @set_filter("xxx")
    @set_eventbridge_event("state_pending")
    def test_process_ec2_state_pending(self):
        with patch("stackstate_checks.aws_topology.AwsTopologyCheck.must_run_full", return_value=False):
            self.check.run()
            self.assert_updated_ok()
            topology = [top.get_snapshot(self.check.check_id)]
            self.assertEqual(len(topology), 1)
            self.assert_updated_ok()
            components = topology[0]["components"]
            top.assert_component(
                components,
                "i-1234567890123456",
                "aws.ec2.instance",
                checks={"InstanceId": "i-1234567890123456"},
            )

    @set_filter("xxx")
    @set_eventbridge_event("state_running")
    def test_process_ec2_state_running(self):
        with patch("stackstate_checks.aws_topology.AwsTopologyCheck.must_run_full", return_value=False):
            self.check.run()
            self.assert_updated_ok()
            events = aggregator.events
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "ec2_state")
            self.assertEqual(events[0]["host"], "i-1234567890123456")
            self.assertEqual(events[0]["msg_text"], "running")
            self.assertEqual(events[0]["msg_title"], "EC2 instance state")
            self.assertEqual(events[0]["msg_text"], "running")
            self.assertEqual(events[0]["tags"], ["state:running"])

    @set_filter("xxx")
    @set_eventbridge_event("state_stopping")
    def test_process_ec2_state_stopping(self):
        with patch("stackstate_checks.aws_topology.AwsTopologyCheck.must_run_full", return_value=False):
            self.check.run()
            topology = [top.get_snapshot(self.check.check_id)]
            self.assertEqual(len(topology), 1)
            self.assert_updated_ok()
            components = topology[0]["components"]
            top.assert_component(
                components,
                "i-1234567890123456",
                "aws.ec2.instance",
                checks={"InstanceId": "i-1234567890123456"},
            )

    @set_filter("xxx")
    @set_eventbridge_event("state_terminated")
    def test_process_ec2_state_terminated(self):
        with patch("stackstate_checks.aws_topology.AwsTopologyCheck.must_run_full", return_value=False):
            self.check.run()
            self.assert_updated_ok()
            self.assertEqual(self.check.delete_ids, ["i-0f70dba7ea83d6dec"])
