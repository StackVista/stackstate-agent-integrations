from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest
from mock import patch


def dont_send_parked_relations(self):
    pass


class TestCloudFormation(BaseApiTest):
    def get_api(self):
        return "cloudformation"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return "eu-west-1"

    @patch(
        "stackstate_checks.aws_topology.aws_topology.AgentProxy.finalize_account_topology", dont_send_parked_relations
    )
    def test_process_cloudformation_stack_relations(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        stack1 = (
            "arn:aws:cloudformation:eu-west-1:731070500579:stack/stackstate-topo-publisher/"
            + "71ea3f80-9919-11e9-a261-0a99a68566c4"
        )

        stack2 = (
            "arn:aws:cloudformation:eu-west-1:731070500579:stack/stackstate-topo-cwevents/"
            + "077bd960-9919-11e9-adb7-02135cc8443e"
        )

        top.assert_component(
            components,
            stack1,
            "aws.cloudformation.stack",
            checks={"LastUpdatedTime": "2019-06-27T20:23:43.548Z", "StackName": "stackstate-topo-publisher"},
        )
        top.assert_component(
            components,
            stack2,
            "aws.cloudformation.stack",
            checks={"LastUpdatedTime": "2019-06-27T20:20:45.336Z", "StackName": "stackstate-topo-cwevents"},
        )

        top.assert_relation(relations, stack2, stack1, "has-resource")

        top.assert_all_checked(components, relations)
