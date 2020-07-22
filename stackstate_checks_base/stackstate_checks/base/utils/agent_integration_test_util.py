
class AgentIntegrationTestUtil(object):

    @staticmethod
    def assert_agent_integration_component(check, integration_component):
        instance = check.check._get_instance_key()
        expected_component = {
            'data': {
                'cluster': 'stubbed-cluster-name',
                'hostname': 'stubbed.hostname',
                'integration': '{}'.format(instance["type"]),
                'name': '{}:{}'.format(instance["type"], instance["url"]),
                'tags': []
            },
            'id': 'urn:integration:stubbed.hostname:{}:{}'.format(instance["type"], instance["url"]),
            'type': 'agent-integration'
        }
        check.assertEqual(expected_component, integration_component)

    @staticmethod
    def assert_agent_integration_relation(check, integration_relation):
        instance = check.check._get_instance_key()
        expected_relation = {
            'data': {},
            'source_id': 'urn:integration:stubbed.hostname:{}:{}'.format(instance["type"], instance["url"]),
            'target_id': integration_relation['target_id'],
            'type': 'agent-integration'
        }
        check.assertEqual(expected_relation, integration_relation)
