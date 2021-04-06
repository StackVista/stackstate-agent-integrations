from ..utils import make_valid_data, correct_tags


def process_vpn_gateways(location_info, client, agent):
    for vpn_description_raw in client.describe_vpn_gateways().get('VpnGateways') or []:
        vpn_description = make_valid_data(vpn_description_raw)
        vpn_id = vpn_description['VpnGatewayId']
        vpn_description.update(location_info)
        agent.component(vpn_id, 'aws.vpngateway', correct_tags(vpn_description))
        if vpn_description.get('VpcAttachments'):
            for vpn_attachment in vpn_description['VpcAttachments']:
                vpc_id = vpn_attachment['VpcId']
                agent.relation(vpn_id, vpc_id, 'uses service', {})
