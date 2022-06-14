import json

import pytest
from schematics import Model
from schematics.types import URLType, ListType, StringType, IntType

from stackstate_checks.base.checks.base import AgentStatefulCheck, StackPackInstance, AgentCheck
from stackstate_checks.base.utils.state_api import generate_state_key

TEST_INSTANCE = {
    "url": "https://example.org/api"
}


class SampleStatefulCheck(AgentStatefulCheck):
    """
    This test class is uses dictionaries for instance and state.
    """
    INSTANCE_TYPE = "stateful_check"

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SampleStatefulCheck, self).__init__(name, init_config, agentConfig, instances)

    def stateful_check(self, instance, state):
        state["key3"] = "ghi"
        return state

    def get_instance_key(self, instance):
        return StackPackInstance(self.INSTANCE_TYPE, instance.get("url", ""))


@pytest.fixture
def sample_stateful_check(state, aggregator):
    check = SampleStatefulCheck('test01', {}, {}, instances=[TEST_INSTANCE])
    yield check
    state.reset()
    aggregator.reset()


class InstanceInfo(Model):
    url = URLType(required=True)
    instance_tags = ListType(StringType, default=[])


class State(Model):
    offset = IntType(default=0)


class SampleStatefulCheckWithSchema(AgentStatefulCheck):
    """
    This class uses instance schema and state schema.
    """
    INSTANCE_TYPE = "stateful_check"
    INSTANCE_SCHEMA = InstanceInfo

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SampleStatefulCheckWithSchema, self).__init__(name, init_config, agentConfig, instances)

    def stateful_check(self, instance, state):
        state = State(state)
        state.validate()
        state.offset += 10
        return state

    def get_instance_key(self, instance):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance.url))


@pytest.fixture
def sample_stateful_check_with_schema(state, aggregator):
    check = SampleStatefulCheckWithSchema('test02', {}, {}, instances=[TEST_INSTANCE])
    yield check
    state.reset()
    aggregator.reset()


class TestStatefulCheck:
    def test_instance_key_generation(self):
        test_instance = {
            'url': 'http://example.org/api?query_string=123&another=456'
        }
        check = SampleStatefulCheck('test01', {}, {}, [test_instance])
        check._init_state_api()
        assert check._state._get_state_key('test_key') == "httpexampleorgapiquery_string123another456_test_key"

    def test_stateful_check(self, sample_stateful_check, state, aggregator):
        sample_stateful_check.run()

        key = get_test_state_key(sample_stateful_check)
        expected_state = {
            "key3": "ghi"
        }
        assert sample_stateful_check.get_state() == expected_state
        assert state.get_state(sample_stateful_check,
                               sample_stateful_check.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check.name, count=1, status=AgentCheck.OK)

    def test_stateful_check_state_exists(self, sample_stateful_check, state, aggregator):
        """
        State is dictionary in SampleStatefulCheck, so we don't have restrictions to modify state structure.
        """
        # setup existing state
        key = get_test_state_key(sample_stateful_check)
        existing_state = '{"key1": "abc", "key2": "def"}'
        state.set_state(sample_stateful_check,
                        sample_stateful_check.check_id,
                        key,
                        existing_state)

        # run check to create new state
        sample_stateful_check.run()
        expected_state = {
            "key1": "abc",
            "key2": "def",
            "key3": "ghi"
        }
        assert sample_stateful_check.get_state() == expected_state
        assert state.get_state(sample_stateful_check,
                               sample_stateful_check.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check.name, count=1, status=AgentCheck.OK)

    def test_stateful_check_with_schema(self, sample_stateful_check_with_schema, state, aggregator):
        sample_stateful_check_with_schema.run()
        key = get_test_state_key(sample_stateful_check_with_schema)
        expected_state = {"offset": 10}
        assert sample_stateful_check_with_schema.get_state() == expected_state
        assert state.get_state(sample_stateful_check_with_schema,
                               sample_stateful_check_with_schema.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheck.OK)

    def test_stateful_check_with_schema_existing_state(self, sample_stateful_check_with_schema, state, aggregator):
        # setup existing state
        key = get_test_state_key(sample_stateful_check_with_schema)
        existing_state = '{"offset": 20}'
        state.set_state(sample_stateful_check_with_schema,
                        sample_stateful_check_with_schema.check_id,
                        key,
                        existing_state)

        # run the check to alter state
        sample_stateful_check_with_schema.run()
        expected_state = {"offset": 30}
        assert sample_stateful_check_with_schema.get_state() == expected_state
        assert state.get_state(sample_stateful_check_with_schema,
                               sample_stateful_check_with_schema.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheck.OK)

    def test_stateful_check_with_invalid_schema(self, sample_stateful_check_with_schema, state, aggregator):
        # setup invalid existing state
        key = get_test_state_key(sample_stateful_check_with_schema)
        existing_state = '{"key_that_is_not_in_schema": "some_value"}'
        state.set_state(sample_stateful_check_with_schema,
                        sample_stateful_check_with_schema.check_id,
                        key,
                        existing_state)

        # run the check that should be critical
        sample_stateful_check_with_schema.run()
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheck.CRITICAL)
        service_check = aggregator.service_checks(sample_stateful_check_with_schema.name)
        # error should Schema validation error
        assert service_check[0].message == '{"key_that_is_not_in_schema": "Rogue field"}'


class TestTransaction:
    def test_transaction_start_and_stop(self, transaction):
        check = SampleStatefulCheck('test01', {}, {}, instances=[{}])
        check._init_transactional_api()
        check.transaction.start()
        check.transaction.stop()
        transaction.assert_transaction(check.check_id)


def get_test_state_key(check):
    return generate_state_key(check.instance["url"], check.PERSISTENT_CACHE_KEY)
