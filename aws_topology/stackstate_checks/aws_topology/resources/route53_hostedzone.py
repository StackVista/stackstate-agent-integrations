from .utils import make_valid_data
from .registry import RegisteredResourceCollector


class Route53HostedzoneCollector(RegisteredResourceCollector):
    API = "route53"
    API_TYPE = "global"
    COMPONENT_TYPE = "aws.route53.hostedzone"

    def process_all(self):
        """
        Route 53 hosted zones contain DNS records. A AWS Domain can point to a hosted zone.
        """
        for list_hosted_zones_page in self.client.get_paginator('list_hosted_zones').paginate():
            for hosted_zone in list_hosted_zones_page.get('HostedZones') or []:
                self.process_hosted_zone(hosted_zone)

    def process_hosted_zone(self, hosted_zone):
        hosted_zone_data = {}
        hosted_zone_id = hosted_zone['Id']
        resource_id = hosted_zone_id.rsplit('/', 1)[-1]
        tags = self.client.list_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=resource_id
        ).get('ResourceTagSet')
        if tags:
            hosted_zone_data['Tags'] = tags.get('Tags') or []
        hosted_zone_data['Id'] = hosted_zone_id
        hosted_zone_detail_raw = self.client.get_hosted_zone(Id=hosted_zone_id)
        hosted_zone_detail = make_valid_data(hosted_zone_detail_raw)
        hosted_zone_data['HostedZone'] = hosted_zone_detail['HostedZone']
        if 'DelegationSet' in hosted_zone_detail:
            hosted_zone_data['DelegationSet'] = hosted_zone_detail['DelegationSet']

        resource_record_sets = self.client.list_resource_record_sets(HostedZoneId=hosted_zone_id)
        hosted_zone_data['ResourceRecordSets'] = resource_record_sets.get('ResourceRecordSets') or []
        hosted_zone_data['URN'] = [
            "arn:aws:route53:::{}".format(hosted_zone_id.lstrip('/'))
        ]
        self.agent.component(hosted_zone_id, self.COMPONENT_TYPE, hosted_zone_data)
