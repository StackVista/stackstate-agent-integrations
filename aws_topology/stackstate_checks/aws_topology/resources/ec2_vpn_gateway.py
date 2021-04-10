from ..utils import make_valid_data
from .registry import RegisteredResource


class vpn_gateway(RegisteredResource):
    API = "ec2"
    COMPONENT_TYPE = "aws.vpngateway"

    def process_all(self):
        for vpn_description_raw in self.client.describe_vpn_gateways().get('VpnGateways') or []:
            vpn_description = make_valid_data(vpn_description_raw)
            self.process_vpn_gateway(vpn_description)

    def process_vpn_gateway(self, vpn_description):
        vpn_id = vpn_description['VpnGatewayId']
        self.agent.component(vpn_id, self.COMPONENT_TYPE, vpn_description)
        if vpn_description.get('VpcAttachments'):
            for vpn_attachment in vpn_description['VpcAttachments']:
                vpc_id = vpn_attachment['VpcId']
                self.agent.relation(vpn_id, vpc_id, 'uses service', {})
