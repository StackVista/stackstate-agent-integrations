from stackstate_checks.base.checks.base import AgentStatefulCheck, StackPackInstance


class SampleStatefulCheck(AgentStatefulCheck):
    INSTANCE_TYPE = 'stateful_check_test'

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SampleStatefulCheck, self).__init__(name, init_config, agentConfig, instances)

    def stateful_check(self, instance, state):
        state['key3'] = 'ghi'
        return state

    def get_instance_key(self, instance):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance.get('url', '')))


class TestStatefulCheck:
    def test_stateful_check(self):
        test_instance = {
            'type': 'stateful_check_test',
            'url': 'https://example.org/api'
        }
        check = SampleStatefulCheck('test01', {}, {}, instances=[test_instance])
        initial_state = {
            'key1': 'abc',
            'key2': 'def'
        }

        check.run()
        assert check.get_state() == {
            # 'key1': 'abc',
            # 'key2': 'def',
            'key3': 'ghi'
        }

    def test_instance_key_url_sanitization(self):
        test_instance = {
            'type': 'stateful_check_test',
            'url': 'https://example.org/api?query_string=123&another=456'
        }
        check = SampleStatefulCheck('test', {}, {}, [test_instance])
        check.run()
        assert check._state._instance_key_url_as_filename() == "httpsexampleorgapiquery_string123another456"


class TestTransaction:
    def test_transaction_start_and_stop(self, transaction):
        check = SampleStatefulCheck('test01', {}, {}, instances=[{}])
        check._init_transactional_api()
        check.transaction.start_transaction()
        check.transaction.stop_transaction()
        transaction.assert_transaction(check.check_id)
