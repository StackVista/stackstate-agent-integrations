# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os
from typing import Dict

import pytest
import requests

from stackstate_checks.dev import docker_run, WaitFor
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import SplunkInstanceConfig
from stackstate_checks.splunk_event import SplunkEvent
from stackstate_checks.splunk_event.splunk_event import default_settings
from .common import HOST, PORT, USER, PASSWORD

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


def _connect_to_splunk():
    SplunkClient(SplunkInstanceConfig(_empty_instance, {}, default_settings)).auth_session({})


@pytest.fixture(scope='session')
def test_environment():
    """
    Start a standalone splunk server requiring authentication.
    """
    with docker_run(
            os.path.join(HERE, 'compose', 'docker-compose.yaml'),
            conditions=[WaitFor(_connect_to_splunk)],
    ):
        yield True


# this fixture is used for checksdev env start
@pytest.fixture(scope='session')
def sts_environment(test_environment):
    """
    This fixture is used for checksdev env start.
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
def integration_test_instance():
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
    # type: (str, str, str) -> str
    """
    Send requests to a Splunk instance for creating `test_events` search.
    The Splunk started with Docker Compose command when we run integration tests.
    """
    search_name = 'test_events'
    source_type = "sts_test_data"

    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (url, search_name), auth=(user, password))

    requests.post("%s/services/saved/searches" % url,
                  data={"name": search_name,
                        "search": 'sourcetype="sts_test_data" '
                                  '| eval status = upper(status) '
                                  '| search status=critical OR status=error OR status=warning OR status=ok '
                                  '| table _time _bkt _cd host status description'},
                  auth=(user, password)).raise_for_status()
    requests.post("%s/services/receivers/simple" % url,
                  params={"host": "host01", "sourcetype": source_type},
                  json={"status": "OK", "description": "host01 test ok event"},
                  auth=(user, password)).raise_for_status()
    requests.post("%s/services/receivers/simple" % url,
                  params={"host": "host02", "sourcetype": source_type},
                  json={"status": "CRITICAL", "description": "host02 test critical event"},
                  auth=(user, password)).raise_for_status(),
    requests.post("%s/services/receivers/simple" % url,
                  params={"host": "host03", "sourcetype": source_type},
                  json={"status": "error", "description": "host03 test error event"},
                  auth=(user, password)).raise_for_status(),
    requests.post("%s/services/receivers/simple" % url,
                  params={"host": "host04", "sourcetype": source_type},
                  json={"status": "warning", "description": "host04 test warning event"},
                  auth=(user, password)).raise_for_status()

    return search_name


@pytest.fixture
def splunk_event_check(unit_test_instance, aggregator, state, transaction):
    check = SplunkEvent("splunk", {}, {}, [unit_test_instance])
    yield check
    aggregator.reset()
    state.reset()
    transaction.reset()


@pytest.fixture
def unit_test_instance():
    return {
        'url': 'http://localhost:8089',
        'authentication': {
            'basic_auth': {
                'username': "admin",
                'password': "admin12345"
            }
        },
        'saved_searches': [
            {
                "name": "test_events",
                "parameters": {},
            }
        ],
        'tags': []
    }


def extract_title_and_type_from_event(event):
    # type: (Dict) -> Dict
    """Extracts event title and type. Method call aggregator.assert_event needs event fields as **kwargs parameter."""
    return {"msg_title": event["msg_title"], "event_type": event["event_type"]}
