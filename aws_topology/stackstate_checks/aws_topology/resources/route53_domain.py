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
from schematics.types import StringType
from copy import deepcopy


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="route53", region="", account_id=account_id, resource_id="domain/" + resource_id)


DomainData = namedtuple("DomainData", ["domain", "tags"])


class Domain(Model):
    DomainName = StringType(required=True)


class Route53DomainCollector(RegisteredResourceCollector):
    API = "route53domains"
    API_TYPE = "global"
    COMPONENT_TYPE = "aws.route53.domain"

    @set_required_access_v2("route53domains:ListTagsForDomain")
    def collect_tags(self, domain_name):
        return self.client.list_tags_for_domain(DomainName=domain_name).get("TagList", [])

    @set_required_access_v2("route53domains:GetDomainDetail")
    def collect_domain_description(self, domain_name):
        return self.client.get_domain_detail(DomainName=domain_name) or {}

    def collect_domain(self, domain_data):
        domain_name = domain_data.get("DomainName", "")
        data = deepcopy(domain_data)
        # ListDomains has some attributes that GetDomainDetail doesn't have, so add to original object
        data.update(self.collect_domain_description(domain_name))
        tags = self.collect_tags(data) or []
        return DomainData(domain=data, tags=tags)

    def collect_domains(self):
        for domain in [
            self.collect_domain(domain_data)
            for domain_data in client_array_operation(self.client, "list_domains", "Domains")
        ]:
            yield domain

    @set_required_access_v2("route53domains:ListDomains")
    def process_domains(self):
        for domain_data in self.collect_domains():
            self.process_domain(domain_data)

    def process_all(self, filter=None):
        """
        Route 53 Domains define which domains are owned by the account.
        """
        if not filter or "domains" in filter:
            self.process_domains()

    @transformation()
    def process_domain(self, data):
        domain = Domain(data.domain, strict=False)
        domain.validate()
        output = make_valid_data(data.domain)
        domain_name = domain.DomainName
        output["Name"] = domain_name
        output["Tags"] = data.tags
        output["URN"] = [
            self.agent.create_arn("AWS::Route53Domains::Domain", self.location_info, resource_id=domain_name)
        ]
        self.emit_component(domain_name, self.COMPONENT_TYPE, output)
