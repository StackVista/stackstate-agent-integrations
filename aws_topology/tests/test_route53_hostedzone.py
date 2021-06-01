from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestRoute53HostedZone(BaseApiTest):

    def get_api(self):
        return "route53"

    def get_account_id(self):
        return "731070500579"
    
    def get_region(self):
        return 'global'

    def test_process_route53_hostedzone(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        self.assert_has_component(
            components,
            "/hostedzone/Z4OKCQBA0VS63",
            "aws.route53.hostedzone",
            checks={
                "URN": [
                    "arn:aws:route53:::hostedzone/Z4OKCQBA0VS63"
                ],
                "Tags.ResourceTagKey": "ResourceTagValue",
                "HostedZone.Name": "serverless.nl."
            }
        )
        self.assert_location_info(topology[0]["components"][0])

        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)
