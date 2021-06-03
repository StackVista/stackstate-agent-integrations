from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestRedshift(BaseApiTest):

    def get_api(self):
        return "redshift"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return 'eu-west-1'

    def test_process_redshift(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        self.assert_has_component(
            components,
            "redshift-cluster-1",
            "aws.redshift"
        )
        self.assert_has_relation(
            relations,
            "redshift-cluster-1",
            "vpc-c6d073bf"
        )

        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)

    @set_cloudtrail_event('create_cluster')
    def test_process_redshift_create_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'redshift-cluster-1',
            topology[0]["components"][0]["id"]
        )

    @set_cloudtrail_event('delete_cluster')
    def test_process_redshift_delete_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('redshift-cluster-1', self.check.delete_ids)
