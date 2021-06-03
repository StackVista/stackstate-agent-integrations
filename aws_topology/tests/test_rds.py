from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestRds(BaseApiTest):

    def get_api(self):
        return "rds"

    def get_account_id(self):
        return "731070500579"

    def test_process_rds(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]
        # cluster
        self.assert_has_component(
            components,
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
            "aws.rds_cluster",
            checks={
                "DBClusterArn": "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
                "Name": "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
                "CW.Dimensions": [
                    {"Key": "DBClusterIdentifier", "Value": "productiondatabasecluster"}
                ]
            }
        )
        # instance 1
        self.assert_has_component(
            components,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase",
            "aws.rds_instance",
        )
        # instance 2
        self.assert_has_component(
            components,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c",
            "aws.rds_instance",
            checks={
                "DBInstanceIdentifier": "productiondatabase-eu-west-1c",
                "Name": "productiondatabase-eu-west-1c",
                "CW.Dimensions": [
                    {"Key": "DBInstanceIdentifier", "Value": "productiondatabase-eu-west-1c"}
                ],
                "URN": [
                    "urn:endpoint:/productiondatabase-eu-west-1c.cdnm1uvvpdkc.eu-west-1.rds.amazonaws.com"
                ]
            }
        )
        # cluster <-> instance-1
        self.assert_has_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase"
        )
        # cluster <-> instance-2
        self.assert_has_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c"
        )
        # instance-1 <-> vpc
        self.assert_has_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase",
            "vpc-6b25d10e"
        )
        # instance-1 <-> security group
        self.assert_has_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase",
            "sg-053ecf78"
        )
        # instance-1 <-> vpc
        self.assert_has_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c",
            "vpc-6b25d10e"
        )
        # instance-1 <-> security group
        self.assert_has_relation(
            relations,
            "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c",
            "sg-053ecf78"
        )
        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)

    @set_cloudtrail_event('create_cluster')
    def test_process_rds_create_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster',
            topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event('delete_cluster')
    def test_process_rds_delete_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn(
            'arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster', self.check.delete_ids)

    @set_cloudtrail_event('create_instance')
    def test_process_rds_create_instance(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:rds:eu-west-1:731070500579:db:productiondatabase',
            topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event('delete_instance')
    def test_process_rds_delete_instance(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn(
            'arn:aws:rds:eu-west-1:731070500579:db:productiondatabase', self.check.delete_ids)
