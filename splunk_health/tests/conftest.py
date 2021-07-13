# (C) Datadog, Inc. 2010-2018
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
import os

import pytest
import requests

from stackstate_checks.dev import WaitFor, docker_run
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import SplunkInstanceConfig
from stackstate_checks.splunk_health.splunk_health import default_settings
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
    'saved_searches': []
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
            "name": _make_health_fixture(url, USER, PASSWORD),
        }]
    }


@pytest.fixture
def splunk_health_instance():
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
            "name": _make_health_fixture(url, USER, PASSWORD),
        }]
    }


def _make_health_fixture(url, user, passw):
    search_name = 'health'
    search = {'name': search_name,
              'search': '* | dedup check_state_id | sort - check_state_id | '
                        'fields check_state_id, name, health, topology_element_identifier, message'}
    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (url, search_name), auth=(user, passw))
    requests.post("%s/services/saved/searches" % url, data=search, auth=(user, passw)).raise_for_status()
    json_data = {"check_state_id": "disk_sda",
                 "name": "Disk sda",
                 "health": "clear",
                 "topology_element_identifier": "component1",
                 "message": "sda message"}
    requests.post("%s/services/receivers/simple" % url, json=json_data, auth=(user, passw)).raise_for_status()
    json_data = {"check_state_id": "disk_sdb",
                 "name": "Disk sdb",
                 "health": "critical",
                 "topology_element_identifier": "component2"}
    requests.post("%s/services/receivers/simple" % url, json=json_data, auth=(user, passw)).raise_for_status()
    return search_name
