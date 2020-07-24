
class AgentIntegrationTestUtil(object):

    @staticmethod
    def expected_agent_integration_component(check, integration_component):
        instance = check._get_instance_key()
        return {
            'data': {
                'cluster': 'stubbed-cluster-name',
                'hostname': 'stubbed.hostname',
                'integration': '{}'.format(instance["type"]),
                'name': '{}:{}'.format(instance["type"], instance["url"]),
                'tags': [],
                'checks': [
                    {
                        'is_service_check_health_check': True,
                        'name': 'Integration Health',
                        'stream_id': integration_component['data']['checks'][0]['stream_id']
                    }
                ],
                'streams': [
                    {
                        'conditions': {
                            'hostname': 'stubbed.hostname',
                            'integration-type': '{}'.format(instance["type"]),
                            'integration-url': '{}'.format(instance["url"])
                        },
                        'identifier': integration_component['data']['streams'][0]['identifier'],
                        'name': 'Service Checks'
                    }
                ]
            },
            'id': 'urn:integration:stubbed.hostname:{}:{}'.format(instance["type"], instance["url"]),
            'type': 'agent-integration',
        }

    @staticmethod
    def assert_agent_integration_component(check, integration_component):
        check.assertEqual(AgentIntegrationTestUtil.expected_agent_integration_component(check.check,
                                                                                        integration_component),
                          integration_component)

    @staticmethod
    def expected_agent_integration_relation(check):
        instance = check._get_instance_key()
        return {
            'data': {},
            'source_id': 'urn:integration:stubbed.hostname:{}:{}'.format(instance["type"], instance["url"]),
            'target_id': 'urn:process/:stubbed.hostname:1:1234567890',
            'type': 'agent-integration'
        }

    @staticmethod
    def assert_agent_integration_relation(check, integration_relation):
        check.assertEqual(AgentIntegrationTestUtil.expected_agent_integration_relation(check.check),
                          integration_relation)
