# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest

from stackstate_checks.base.errors import CheckException
from .mock import MockedSplunkEvent, MockedSplunkClient


@pytest.fixture(scope='session')
def sts_environment():
    # This conf instance is used when running `checksdev env start mycheck myenv`.
    # The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    # If you want to run an environment this object can not be empty.
    return {"key": "value"}


@pytest.fixture
def instance():
    return {
        'url': 'http://localhost:8089',
        'authentication': {
            'basic_auth': {
                'username': "admin",
                'password': "admin"
            }
        },
        'saved_searches': [],
        'tags': []
    }


@pytest.fixture
def mocked_check(instance, aggregator, state, transaction):
    check = MockedSplunkEvent("splunk_event", {}, {}, [instance])
    yield check
    aggregator.reset()
    state.reset()
    transaction.reset()


@pytest.fixture
def fatal_error(instance):
    instance['saved_searches'] = [{
        "name": "error",
        "parameters": {}
    }]


@pytest.fixture
def empty_result(instance):
    instance['saved_searches'] = [{
        "name": "empty",
        "parameters": {}
    }]


@pytest.fixture
def minimal_events(instance):
    instance['saved_searches'] = [{
        "name": "minimal_events",
        "parameters": {}
    }]


@pytest.fixture
def full_events(instance):
    instance['saved_searches'] = [{
        "name": "full_events",
        "parameters": {}
    }]
    instance['tags'] = ["checktag:checktagvalue"]


@pytest.fixture
def partially_incomplete_events(instance):
    instance['saved_searches'] = [{
        "name": "partially_incomplete_events",
        "parameters": {}
    }]


@pytest.fixture(scope="function")
def earliest_time_and_duplicates(instance, monkeypatch):
    instance['saved_searches'] = [{
        "name": "poll",
        "parameters": {},
        "batch_size": 2
    }]
    instance['tags'] = ["checktag:checktagvalue"]

    test_data = {
        "expected_searches": ["poll"],
        "sid": "",
        "time": 0,
        "earliest_time": "",
        "throw": False
    }

    def _mocked_current_time_seconds():
        return test_data["time"]

    def _mocked_dispatch(saved_search, splunk_app, ignore_saved_search_errors, parameters):
        if test_data["throw"]:
            raise CheckException("Is broke it")
        earliest_time = parameters['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]

        ignore_saved_search_flag = ignore_saved_search_errors
        # make sure to ignore search flag is always false
        assert ignore_saved_search_flag is False

        return test_data["sid"]

    monkeypatch.setattr(MockedSplunkClient, "dispatch", _mocked_dispatch)
    monkeypatch.setattr(MockedSplunkEvent, "_current_time_seconds", _mocked_current_time_seconds)
