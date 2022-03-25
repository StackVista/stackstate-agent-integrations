from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestRedshift(BaseApiTest):
    def get_api(self):
        return "redshift"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return "eu-west-1"

    def test_process_redshift(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        top.assert_component(
            components,
            "arn:aws:redshift:eu-west-1:731070500579:cluster:redshift-cluster-1",
            "aws.redshift.cluster",
            checks={
                "Name": "redshift-cluster-1",
                "Tags.OrganizationalUnit": "Testing",
                "URN": ["arn:aws:redshift:eu-west-1:731070500579:cluster:redshift-cluster-1"],
            },
        )
        top.assert_relation(
            relations,
            "arn:aws:redshift:eu-west-1:731070500579:cluster:redshift-cluster-1",
            "vpc-c6d073bf",
            "uses-service",
        )

        top.assert_all_checked(components, relations)

    @set_cloudtrail_event("create_cluster")
    def test_process_redshift_create_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:redshift:eu-west-1:731070500579:cluster:redshift-cluster-1", topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event("delete_cluster")
    def test_process_redshift_delete_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn("arn:aws:redshift:eu-west-1:731070500579:cluster:redshift-cluster-1", self.check.delete_ids)
        topology = top.get_snapshot(self.check.check_id)
        assert topology["delete_ids"] == ["arn:aws:redshift:eu-west-1:731070500579:cluster:redshift-cluster-1"]
