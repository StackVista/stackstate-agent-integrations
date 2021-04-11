# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import unittest
from mock import patch
from copy import deepcopy

from stackstate_checks.base.stubs import topology, aggregator
from stackstate_checks.base import AgentCheck
from stackstate_checks.aws_topology import AwsTopologyCheck

from .test_aws_topology import API_RESULTS

SIMPLE_VPN_GATEWAY = {
    'DescribeVpnGateways': {
        "VpnGateways": [
            {
                "State": "available",
                "Type": "ipsec.1",
                "VpnGatewayId": "vgw-b8c2fccc",
                "AmazonSideAsn": 9059,
            }
        ]
    }
}


@pytest.mark.usefixtures("instance")
class TestVpnGateway(unittest.TestCase):
    """Basic Test for AWS Topology integration."""

    CHECK_NAME = 'aws_topology'
    SERVICE_CHECK_NAME = "aws_topology"

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        config = {}
        self.patcher = patch('botocore.client.BaseClient._make_api_call')
        self.mock_object = self.patcher.start()
        self.api_results = deepcopy(API_RESULTS)
        topology.reset()
        aggregator.reset()
        self.check = AwsTopologyCheck(self.CHECK_NAME, config, instances=[self.instance])

        def results(operation_name, kwarg):
            return self.api_results.get(operation_name) or {}

        self.mock_object.side_effect = results

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK)

    def test_simple_vpn_gateway(self):
        self.api_results.update(SIMPLE_VPN_GATEWAY)
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['components']), 1)
        self.assertEqual(test_topology['components'][0]['type'], 'aws.vpngateway')
        self.assertEqual(test_topology['components'][0]['id'], 'vgw-b8c2fccc')
        self.assert_executed_ok()

    def test_vpn_gateway_with_attachments(self):
        self.api_results.update(SIMPLE_VPN_GATEWAY)
        self.api_results['DescribeVpnGateways']['VpnGateways'][0].update({
            "VpcAttachments": [
                {
                    "State": "attached",
                    "VpcId": "vpc-6b25d10e"
                }
            ]
        })
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['relations']), 1)
        self.assertEqual(
            test_topology['relations'][0],
            {'source_id': 'vgw-b8c2fccc', 'target_id': 'vpc-6b25d10e', 'type': 'uses service', 'data': {}}
        )
        self.assert_executed_ok()

    def test_vpm_gateway_with_tags(self):
        self.api_results.update(SIMPLE_VPN_GATEWAY)
        self.api_results['DescribeVpnGateways']['VpnGateways'][0].update({
            "Tags": [
                {
                    "Key": "Name",
                    "Value": "my-first-vpn-gateway"
                }
            ]
        })
        self.check.run()
        test_topology = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(test_topology['components']), 1)
        self.assertIsNotNone(test_topology['components'][0]['data'])
        self.assertEqual(test_topology['components'][0]['data']['Tags'], {'Name': 'my-first-vpn-gateway'})
        self.assert_executed_ok()
