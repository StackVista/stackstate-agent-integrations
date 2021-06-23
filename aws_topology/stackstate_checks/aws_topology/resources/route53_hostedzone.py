from .utils import (
    make_valid_data,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ModelType, ListType


def create_arn(resource_id=None, **kwargs):
    return arn(resource="route53", region="", account_id="", resource_id="hostedzone/" + resource_id)


class HostedZoneInfo(Model):
    Id = StringType(required=True)
    Name = StringType(default="")


class HostedZone(Model):
    class HostedZoneDelegationSet(Model):
        Id = StringType()
        NameServers = ListType(StringType(), required=True)

    class HostedZoneVPCs(Model):
        VPCId = StringType(required=True)

    HostedZone = ModelType(HostedZoneInfo, required=True)
    DelegationSet = ModelType(HostedZoneDelegationSet)
    VPCs = ListType(ModelType(HostedZoneVPCs))


HostedZoneData = namedtuple("HostedZoneData", ["hosted_zone", "tags", "resource_record_sets"])


class Route53HostedzoneCollector(RegisteredResourceCollector):
    API = "route53"
    API_TYPE = "global"
    COMPONENT_TYPE = "aws.route53.hostedzone"

    @set_required_access_v2("route53:ListTagsForResource")
    def collect_tags(self, hosted_zone_id):
        return (
            self.client.list_tags_for_resource(ResourceType="hostedzone", ResourceId=hosted_zone_id)
            .get("ResourceTagSet", {})
            .get("Tags", [])
        )

    @set_required_access_v2("route53:GetHostedZone")
    def collect_hosted_zone_description(self, hosted_zone_id):
        return self.client.get_hosted_zone(Id=hosted_zone_id) or {}

    @set_required_access_v2("route53:ListResourceRecordSets")
    def collect_resource_record_sets(self, hosted_zone_id):
        return self.client.list_resource_record_sets(HostedZoneId=hosted_zone_id).get("ResourceRecordSets", [])

    def construct_hosted_zone_description(self, hosted_zone_data):
        return {"HostedZone": hosted_zone_data, "DelegationSet": {}, "VPCs": []}

    def collect_hosted_zone(self, hosted_zone_data):
        hosted_zone_id = hosted_zone_data.get("Id", "").rsplit("/", 1)[-1]  # Remove /hostedzone/
        data = self.collect_hosted_zone_description(hosted_zone_id) or self.construct_hosted_zone_description(
            hosted_zone_data
        )
        tags = self.collect_tags(hosted_zone_id) or []
        resource_record_sets = self.collect_resource_record_sets(hosted_zone_id) or []
        return HostedZoneData(hosted_zone=data, tags=tags, resource_record_sets=resource_record_sets)

    def collect_hosted_zones(self):
        for hosted_zone in [
            self.collect_hosted_zone(hosted_zone_data)
            for hosted_zone_data in client_array_operation(self.client, "list_hosted_zones", "HostedZones")
        ]:
            yield hosted_zone

    @set_required_access_v2("route53:ListHostedZones")
    def process_hosted_zones(self):
        for hosted_zone_data in self.collect_hosted_zones():
            self.process_hosted_zone(hosted_zone_data)

    def process_all(self, filter=None):
        """
        Route 53 hosted zones contain DNS records. A AWS Domain can point to a hosted zone.
        """
        if not filter or "hostedzones" in filter:
            self.process_hosted_zones()

    @transformation()
    def process_hosted_zone(self, data):
        hosted_zone = HostedZone(data.hosted_zone, strict=False)
        hosted_zone.validate()
        output = make_valid_data(data.hosted_zone)
        hosted_zone_id = hosted_zone.HostedZone.Id.rsplit("/", 1)[-1]
        # If no name is found, fallback to hosted zone ID
        output["Name"] = hosted_zone.HostedZone.Name.strip(".") or hosted_zone_id
        output["Tags"] = data.tags
        output["ResourceRecordSets"] = data.resource_record_sets
        output["URN"] = [
            self.agent.create_arn("AWS::Route53::HostedZone", self.location_info, resource_id=hosted_zone_id)
        ]
        self.emit_component(hosted_zone_id, self.COMPONENT_TYPE, output)
