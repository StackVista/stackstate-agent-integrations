
from ..stubs import topology
from .. import TopologyInstance


class AgentIntegrationTestUtil(object):

    @staticmethod
    def expected_agent_component(check):
        return {
            'data': {
                'cluster': 'stubbed-cluster-name',
                'hostname': 'stubbed.hostname',
                'name': 'StackState Agent:stubbed.hostname',
                'tags': sorted(['hostname:stubbed.hostname', 'stackstate-agent']),
                'identifiers': ['urn:process:/stubbed.hostname:1:1234567890'],
            },
            'id': 'urn:stackstate-agent:/stubbed.hostname',
            'type': 'stackstate-agent',
        }

    @staticmethod
    def assert_agent_component(check, agent_component):
        check.assertEqual(AgentIntegrationTestUtil.expected_agent_component(check.check), agent_component)

    @staticmethod
    def expected_agent_integration_component(check, integration_component):
        instance = check._get_instance_key_dict()
        return {
            'data': {
                'cluster': 'stubbed-cluster-name',
                'hostname': 'stubbed.hostname',
                'integration': '{}'.format(instance["type"]),
                'name': 'stubbed.hostname:{}'.format(instance["type"]),
                'tags': sorted(['integration-type:{}'.format(instance["type"]), 'hostname:stubbed.hostname']),
                'checks': [
                    {
                        'is_service_check_health_check': True,
                        'name': 'Integration Health',
                        'stream_id': -1,
                    }
                ],
                'service_checks': [
                    {
                        'conditions': [
                            {'key': 'host', 'value': 'stubbed.hostname'},
                            {'key': 'tags.integration-type', 'value': '{}'.format(instance["type"])},
                        ],
                        'stream_id': -1,
                        'name': 'Service Checks'
                    }
                ],
            },
            'id': 'urn:agent-integration:/stubbed.hostname:{}'.format(instance["type"]),
            'type': 'agent-integration',
        }

    @staticmethod
    def assert_agent_integration_component(check, integration_component):
        check.assertEqual(AgentIntegrationTestUtil.expected_agent_integration_component(check.check,
                                                                                        integration_component),
                          integration_component)

    @staticmethod
    def expected_agent_integration_relation(check):
        instance = check._get_instance_key_dict()
        return {
            'data': {},
            'target_id': 'urn:agent-integration:/stubbed.hostname:{}'.format(instance["type"]),
            'source_id': 'urn:stackstate-agent:/stubbed.hostname',
            'type': 'runs'
        }

    @staticmethod
    def assert_agent_integration_relation(check, integration_relation):
        check.assertEqual(AgentIntegrationTestUtil.expected_agent_integration_relation(check.check),
                          integration_relation)

    @staticmethod
    def expected_agent_integration_instance_component(check, integration_component):
        instance = check._get_instance_key_dict()
        return {
            'data': {
                'cluster': 'stubbed-cluster-name',
                'hostname': 'stubbed.hostname',
                'integration': '{}'.format(instance["type"]),
                'name': '{}:{}'.format(instance["type"], instance["url"]),
                'tags': sorted(['integration-url:{}'.format(instance["url"]),
                                'integration-type:{}'.format(instance["type"]),
                                'hostname:stubbed.hostname']),
                'checks': [
                    {
                        'is_service_check_health_check': True,
                        'name': 'Integration Instance Health',
                        'stream_id': -1,
                    }
                ],
                'service_checks': [
                    {
                        'conditions': [
                            {'key': 'host', 'value': 'stubbed.hostname'},
                            {'key': 'tags.integration-type', 'value': '{}'.format(instance["type"])},
                            {'key': 'tags.integration-url', 'value': '{}'.format(instance["url"])},
                        ],
                        'stream_id': -1,
                        'name': 'Service Checks'
                    }
                ],
            },
            'id': 'urn:agent-integration-instance:/stubbed.hostname:{}:{}'.format(instance["type"], instance["url"]),
            'type': 'agent-integration-instance',
        }

    @staticmethod
    def assert_agent_integration_instance_component(check, integration_instance_component):
        check.assertEqual(
            AgentIntegrationTestUtil.expected_agent_integration_instance_component(check.check,
                                                                                   integration_instance_component),
            integration_instance_component
        )

    @staticmethod
    def expected_agent_integration_instance_relation(check):
        instance = check._get_instance_key_dict()
        return {
            'data': {},
            'target_id': 'urn:agent-integration-instance:/stubbed.hostname:{}:{}'.format(instance["type"],
                                                                                         instance["url"]),
            'source_id': 'urn:agent-integration:/stubbed.hostname:{}'.format(instance["type"]),
            'type': 'has'
        }

    @staticmethod
    def assert_agent_integration_instance_relation(check, integration_instance_relation):
        check.assertEqual(AgentIntegrationTestUtil.expected_agent_integration_instance_relation(check.check),
                          integration_instance_relation)

    @staticmethod
    def assert_integration_snapshot(check, check_id):
        agent_integration_topology_instances = topology.get_snapshot(check_id)
        topology.assert_snapshot(
            check_id=check_id,
            start_snapshot=False,
            stop_snapshot=False,
            instance_key=TopologyInstance("agent", "integrations"),
            components=[
                AgentIntegrationTestUtil.expected_agent_component(check),
                AgentIntegrationTestUtil.
                expected_agent_integration_component(check, agent_integration_topology_instances['components'][1]),
                AgentIntegrationTestUtil.
                expected_agent_integration_instance_component(check,
                                                              agent_integration_topology_instances['components'][2]),
            ],
            relations=[
                AgentIntegrationTestUtil.expected_agent_integration_relation(check),
                AgentIntegrationTestUtil.expected_agent_integration_instance_relation(check)
            ],
        )
