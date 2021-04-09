from ..utils import make_valid_data, correct_tags


def process_route_53_domains(location_info, client, agent):
    """
    Route 53 Domains define which domains are owned by the account.
    """
    for list_domains_page in client.get_paginator('list_domains').paginate():
        for domain_raw in list_domains_page.get('Domains') or []:
            domain = make_valid_data(domain_raw)
            domain_name = domain['DomainName']
            domain['Tags'] = client.list_tags_for_domain(DomainName=domain_name).get('TagList') or []
            domain.update(location_info)
            domain['URN'] = [
                "arn:aws:route53::{}:domain/{}".format(location_info['AwsAccount'], domain_name)
            ]
            agent.component(domain_name, 'aws.route53.domain', correct_tags(domain))
