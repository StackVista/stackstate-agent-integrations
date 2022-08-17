# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

import pytest
import requests

from stackstate_checks.base.errors import CheckException
from stackstate_checks.dev import docker_run, WaitFor
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import SplunkInstanceConfig
from stackstate_checks.splunk_event import SplunkEvent
from stackstate_checks.splunk_event.splunk_event import default_settings
from .common import HOST, PORT, USER, PASSWORD
from .mock import MockedSplunkEvent, MockedSplunkClient

HERE = os.path.dirname(os.path.abspath(__file__))

_empty_instance = {
    'url': 'http://%s:%s' % (HOST, PORT),
    'authentication': {
        'basic_auth': {
            'username': USER,
            'password': PASSWORD
        },
    },
    'saved_searches': [],
    'collection_interval': 15
}


def connect_to_splunk():
    SplunkClient(SplunkInstanceConfig(_empty_instance, {}, default_settings)).auth_session({})


@pytest.fixture(scope='session')
def test_environment():
    """
    Start a standalone splunk server requiring authentication.
    """
    with docker_run(
            os.path.join(HERE, 'compose', 'docker-compose.yaml'),
            conditions=[WaitFor(connect_to_splunk)],
    ):
        yield True


# this fixture is used for checksdev env start
@pytest.fixture(scope='session')
def sts_environment(test_environment):
    """
    Start a standalone splunk server requiring authentication.
    """
    url = 'http://%s:%s' % (HOST, PORT)
    yield {
        'url': url,
        'authentication': {
            'basic_auth': {
                'username': USER,
                'password': PASSWORD
            },
        },
        'saved_searches': [{
            "name": _make_event_fixture(url, USER, PASSWORD),
        }],
        'collection_interval': 15
    }


@pytest.fixture
def splunk_event_instance():
    url = 'http://%s:%s' % (HOST, PORT)
    return {
        'url': url,
        'authentication': {
            'basic_auth': {
                'username': USER,
                'password': PASSWORD
            },
        },
        'saved_searches': [{
            "name": _make_event_fixture(url, USER, PASSWORD),
        }],
        'collection_interval': 15
    }


def _make_event_fixture(url, user, password):
    search_name = 'test_events'
    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (url, search_name), auth=(user, password))
    requests.post("%s/services/saved/searches" % url,
                  data={"name": search_name,
                        "search": "index=main "
                                  "| eval status = upper(status) "
                                  "| search status=CRITICAL OR status=error OR status=warning OR status=OK "
                                  "| table _time hostname status description"},
                  auth=(user, password)).raise_for_status()
    requests.post("%s/services/receivers/simple" % url,
                  json={"event_type": "some_type",
                        "status": "OK",
                        "hostname": "host01",
                        "description": "host01 test ok event",
                        "_time": "2099-12-08T18:29:56.000+00:00"},
                  auth=(user, password)).raise_for_status()
    requests.post("%s/services/receivers/simple" % url,
                  json={"event_type": "some_type",
                        "status": "CRITICAL",
                        "hostname": "host02",
                        "description": "host02 test critical event",
                        "_time": "2099-12-08T18:30:56.000+00:00"},
                  auth=(user, password)).raise_for_status(),
    requests.post("%s/services/receivers/simple" % url,
                  json={"event_type": "some_type",
                        "status": "error",
                        "hostname": "host03",
                        "description": "host03 test error event",
                        "_time": "2099-12-08T18:31:56.000+00:00"},
                  auth=(user, password)).raise_for_status(),
    requests.post("%s/services/receivers/simple" % url,
                  json={"event_type": "some_type",
                        "status": "warning",
                        "hostname": "host04",
                        "description": "host03 test warning event",
                        "_time": "2099-12-08T18:32:56.000+00:00"},
                  auth=(user, password)).raise_for_status()

    return search_name


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


@pytest.fixture
def splunk_event_check(local_splunk, aggregator, state, transaction):
    check = SplunkEvent("splunk", {}, {}, [local_splunk])
    yield check
    aggregator.reset()
    state.reset()
    transaction.reset()


@pytest.fixture
def local_splunk():
    return {
        'url': 'http://localhost:8089',
        'authentication': {
            'basic_auth': {
                'username': "admin",
                'password': "admin12345"
            }
        },
        'saved_searches': [],
        'tags': []
    }
