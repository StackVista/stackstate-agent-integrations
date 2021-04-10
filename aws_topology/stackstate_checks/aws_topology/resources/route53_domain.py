from ..utils import make_valid_data
from .registry import RegisteredResource


class route53_domain(RegisteredResource):
    API = "route53domains"
    COMPONENT_TYPE = "aws.route53.domain"

    def process_all(self):
        """
        Route 53 Domains define which domains are owned by the account.
        """
        for list_domains_page in self.client.get_paginator('list_domains').paginate():
            for domain_raw in list_domains_page.get('Domains') or []:
                domain = make_valid_data(domain_raw)
                self.process_domain(domain)

    def process_domain(self, domain):
        domain_name = domain['DomainName']
        domain['Tags'] = self.client.list_tags_for_domain(DomainName=domain_name).get('TagList') or []
        domain['URN'] = [
            "arn:aws:route53::{}:domain/{}".format(self.location_info['Location']['AwsAccount'], domain_name)
        ]
        self.agent.component(domain_name, self.COMPONENT_TYPE, domain)
