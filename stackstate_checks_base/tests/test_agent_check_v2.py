# -*- coding: utf-8 -*-

# (C) StackState, Inc. 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import pytest
from schematics import Model
from schematics.types import URLType, ListType, StringType, IntType
from stackstate_checks.checks import AgentCheckV2, Transactional, Stateful, StackPackInstance
from stackstate_checks.base.utils.state_api import generate_state_key

TEST_INSTANCE = {
    "url": "https://example.org/api"
}


class SampleStatefulCheck(Stateful, AgentCheckV2):
    """
    This test class is uses dictionaries for instance and state.
    """
    INSTANCE_TYPE = "stateful_check"

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SampleStatefulCheck, self).__init__(name, init_config, agentConfig, instances)

    def stateful_check(self, instance, state):
        state["key3"] = "ghi"
        return state, None

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


class SampleStatefulCheckWithSchema(Stateful, AgentCheckV2):
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
        return state, None

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
        assert check._state._get_state_key('test_key') == "stateful_check_httpexampleorgapiquery_string123another456_test_key"

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
        aggregator.assert_service_check(sample_stateful_check.name, count=1, status=AgentCheckV2.OK)

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
        aggregator.assert_service_check(sample_stateful_check.name, count=1, status=AgentCheckV2.OK)

    def test_stateful_check_with_schema(self, sample_stateful_check_with_schema, state, aggregator):
        sample_stateful_check_with_schema.run()
        key = get_test_state_key(sample_stateful_check_with_schema)
        expected_state = {"offset": 10}
        assert sample_stateful_check_with_schema.get_state() == expected_state
        assert state.get_state(sample_stateful_check_with_schema,
                               sample_stateful_check_with_schema.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheckV2.OK)

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
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheckV2.OK)

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
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheckV2.CRITICAL)
        service_check = aggregator.service_checks(sample_stateful_check_with_schema.name)
        # error should Schema validation error
        assert service_check[0].message == '{"key_that_is_not_in_schema": "Rogue field"}'


class NormalCheck(AgentCheckV2):
    def __init__(self, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(NormalCheck, self).\
            __init__("test", {}, instances)

    def check(self, instance):
        print 'NormalCheck Run'

        return


class TransactionalCheck(Transactional, AgentCheckV2):
    def __init__(self, key=None, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(TransactionalCheck, self). \
            __init__("test", {}, instances)

    def get_instance_key(self, instance):
        return StackPackInstance("test", "transactional")

    def transactional_check(self, instance, state):
        print 'TransactionalCheck Run'
        return state, None


class StatefulCheck(Stateful, AgentCheckV2):
    def __init__(self, key=None, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(StatefulCheck, self). \
            __init__("test", {}, instances)

    def get_instance_key(self, instance):
        return StackPackInstance("test", "stateful")

    def stateful_check(self, instance, state):
        print 'StatefulCheck Run'

        state['updated'] = True

        return state, None


class TransactionalStateCheck(Transactional, AgentCheckV2):
    def __init__(self, key=None, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(TransactionalStateCheck, self). \
            __init__("test", {}, instances)

    def get_instance_key(self, instance):
        return StackPackInstance("test", "transactional-state")

    def transactional_check(self, instance, state):
        print 'TransactionalStateCheck Run'

        state['transactional'] = True

        self.set_state({"state": "set_state"})

        return state, None


def get_test_state_key(check, key=None):
    if key is None:
        key = check.PERSISTENT_CACHE_KEY

    return generate_state_key(check._get_instance_key().to_string(), key)


class TestAgentChecksV2:

    def test_normal_check(self):
        check = NormalCheck()
        check.run()

    def test_transactional_check(self, transaction):
        check = TransactionalCheck()
        assert check.run() is ""

        transaction.assert_transaction(check.check_id)

    def test_stateful_check(self, state):
        check = StatefulCheck()
        check.run()

        expected_state = {
            "updated": True
        }

        key = get_test_state_key(check)
        assert state.get_state(check, check.check_id, key) == json.dumps(expected_state)

    def test_transactional_state_check(self, transaction, state):
        check = TransactionalStateCheck()
        assert check.run() is ""

        transaction.assert_transaction(check.check_id)

        expected_transactional_state = {
            "transactional": True
        }

        key = get_test_state_key(check, check.TRANSACTIONAL_PERSISTENT_CACHE_KEY)
        assert state.get_state(check, check.check_id, key) == json.dumps(expected_transactional_state)

        expected_state = {"state": "set_state"}

        key = get_test_state_key(check)
        assert state.get_state(check, check.check_id, key) == json.dumps(expected_state)
