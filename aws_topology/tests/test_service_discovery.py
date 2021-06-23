from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest


class TestServiceDiscovery(BaseApiTest):
    def get_api(self):
        return "servicediscovery"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return "eu-west-1"

    def test_process_service_discovery(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        top.assert_relation(
            relations,
            "arn:aws:ecs:eu-west-1:731070500579:service/sample-app-service",
            "Z08264772EZNA9MYBM2OH",
            "uses service",
        )
        top.assert_relation(
            relations,
            "i-1234567890123456",
            "Z08264772EZNA9MYBM2OH",
            "uses service",
        )

        top.assert_all_checked(components, relations)
