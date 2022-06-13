from stackstate_checks.base.checks.base import AgentStatefulCheck, StackPackInstance
from stackstate_checks.base.utils.common import sanitize_url_as_valid_filename


class SampleStatefulCheck(AgentStatefulCheck):
    INSTANCE_TYPE = "stateful_check_test"

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SampleStatefulCheck, self).__init__(name, init_config, agentConfig, instances)

    def stateful_check(self, instance, state):
        state["key3"] = "ghi"
        return state

    def get_instance_key(self, instance):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance.get("url", "")))


TEST_INSTANCE = {
    "type": "stateful_check_test",
    "url": "https://example.org/api"
}


class TestStatefulCheck:
    def test_stateful_check(self, state):
        check = SampleStatefulCheck("test01", {}, {}, instances=[TEST_INSTANCE])
        check.run()
        assert check.get_state() == {
            "key3": "ghi"
        }

    def test_stateful_check_state_exists(self, state):
        check = SampleStatefulCheck("test01", {}, {}, instances=[TEST_INSTANCE])

        # setup existing state
        key = "{}_{}".format(sanitize_url_as_valid_filename(TEST_INSTANCE["url"]), check.PERSISTENT_CACHE_KEY)
        existing_state = '{"key1": "abc", "key2": "def"}'
        state.set_state(check, check.check_id, key, existing_state)

        check.run()
        assert check.get_state() == {
            "key1": "abc",
            "key2": "def",
            "key3": "ghi"
        }

    def test_instance_key_generation(self):
        test_instance = {
            'type': 'stateful_check_test',
            'url': 'http://example.org/api?query_string=123&another=456'
        }
        check = SampleStatefulCheck('test', {}, {}, [test_instance])
        check.run()
        assert check._state._state_id('test_key') == "httpexampleorgapiquery_string123another456_test_key"


class TestTransaction:
    def test_transaction_start_and_stop(self, transaction):
        check = SampleStatefulCheck('test01', {}, {}, instances=[{}])
        check._init_transactional_api()
        check.transaction.start_transaction()
        check.transaction.stop_transaction()
        transaction.assert_transaction(check.check_id)
