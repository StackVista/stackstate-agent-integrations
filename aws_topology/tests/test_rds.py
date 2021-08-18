from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event
from stackstate_checks.aws_topology.resources.rds import create_cluster_arn
from mock import patch


class TestRds(BaseApiTest):
    def get_api(self):
        return "rds"

    def get_account_id(self):
        return "731070500579"

    def test_process_rds(self):
        with patch('socket.getaddrinfo', return_value=((0, 0, 0, 0, ['10.1.1.10']),)):
            self.check.run()

        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]
        # cluster
        top.assert_component(
            components,
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
            "aws.rds.cluster",
            checks={
                "DBClusterArn": "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
                "Name": "productiondatabasecluster",
                "CW.Dimensions": [{"Key": "DBClusterIdentifier", "Value": "productiondatabasecluster"}],
                "Tags.testing": "test",
                "URN": [
                    'urn:endpoint:/productiondatabasecluster.cluster-cdnm1uvvpdkc.eu-west-1.rds.amazonaws.com',
                    'urn:endpoint:/productiondatabasecluster.cluster-ro-cdnm1uvvpdkc.eu-west-1.rds.amazonaws.com'
                ],
            },
        )
        # instance 1
        top.assert_component(
            components,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase",
            "aws.rds.instance",
        )
        # instance 2
        top.assert_component(
            components,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c",
            "aws.rds.instance",
            checks={
                "DBInstanceIdentifier": "productiondatabase-eu-west-1c",
                "Name": "productiondatabase-eu-west-1c",
                "CW.Dimensions": [{"Key": "DBInstanceIdentifier", "Value": "productiondatabase-eu-west-1c"}],
                "URN": [
                    "urn:endpoint:/productiondatabase-eu-west-1c.cdnm1uvvpdkc.eu-west-1.rds.amazonaws.com",
                    "urn:vpcip:vpc-6b25d10e/10.1.1.10"
                ],
            },
        )
        # cluster <-> instance-1
        top.assert_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase",
            "has_cluster_node",
        )
        # cluster <-> instance-2
        top.assert_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c",
            "has_cluster_node",
        )
        # instance-1 <-> vpc
        top.assert_relation(
            relations, "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase", "vpc-6b25d10e", "uses-service"
        )
        # instance-1 <-> security group
        top.assert_relation(
            relations, "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase", "sg-053ecf78", "uses-service"
        )
        # instance-1 <-> vpc
        top.assert_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c",
            "vpc-6b25d10e",
            "uses-service",
        )
        # instance-1 <-> security group
        top.assert_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c",
            "sg-053ecf78",
            "uses-service",
        )

        top.assert_all_checked(components, relations)

    def test_process_rds_test_arn_constuctor(self):
        self.assertEqual(
            create_cluster_arn(region="region", account_id="1234567789012", resource_id="mycluster"),
            "arn:aws:rds:region:1234567789012:cluster:mycluster",
        )

    @set_cloudtrail_event("create_cluster")
    def test_process_rds_create_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster", topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event("delete_cluster")
    def test_process_rds_delete_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn("arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster", self.check.delete_ids)

    @set_cloudtrail_event("create_instance")
    def test_process_rds_create_instance(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual("arn:aws:rds:eu-west-1:731070500579:db:productiondatabase", topology[0]["components"][0]["id"])

    @set_cloudtrail_event("delete_instance")
    def test_process_rds_delete_instance(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn("arn:aws:rds:eu-west-1:731070500579:db:productiondatabase", self.check.delete_ids)
