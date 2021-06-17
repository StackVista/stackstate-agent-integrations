from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest


class TestRoute53Domain(BaseApiTest):
    def get_api(self):
        return "route53domains"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return "global"

    def test_process_route53_domain(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        top.assert_component(
            components,
            "stackstate.com",
            "aws.route53.domain",
            checks={
                "URN": ["arn:aws:route53::731070500579:domain/stackstate.com"],
                "Tags.Route53DomainTagKey": "Route53DomainTagValue",
                "DomainName": "stackstate.com",
            },
        )
        self.assert_location_info(topology[0]["components"][0])

        top.assert_all_checked(components, relations)
