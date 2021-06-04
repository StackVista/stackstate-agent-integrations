# (C) Datadog, Inc. 2010-2018
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
import os

import pytest
import requests

from stackstate_checks.dev import WaitFor, docker_run
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk_topology.splunk_topology import InstanceConfig
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
    'component_saved_searches': [],
    'relation_saved_searches': [],
    'tags': ['mytag', 'mytag2']
}


def connect_to_splunk():
    SplunkClient(InstanceConfig(_empty_instance, {})).auth_session()


@pytest.fixture(scope='session')
def test_environment():
    """
    Start a standalone postgres server requiring authentication.
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
    Start a standalone postgres server requiring authentication.
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
        'component_saved_searches': [{
            "name": _make_components_fixture(url, USER, PASSWORD),
        }],
        'relation_saved_searches': [{
            "name": _make_relations_fixture(url, USER, PASSWORD),
        }],
        'tags': ['mytag', 'mytag2']
    }


@pytest.fixture
def splunk_components_instance():
    url = 'http://%s:%s' % (HOST, PORT)
    return {
        'url': url,
        'authentication': {
            'basic_auth': {
                'username': USER,
                'password': PASSWORD
            },
        },
        'component_saved_searches': [{
            "name": _make_components_fixture(url, USER, PASSWORD),
        }],
        'relation_saved_searches': [],
        'tags': ['mytag', 'mytag2']
    }


@pytest.fixture
def splunk_relations_instance():
    url = 'http://%s:%s' % (HOST, PORT)
    return {
        'url': url,
        'authentication': {
            'basic_auth': {
                'username': USER,
                'password': PASSWORD
            },
        },
        'component_saved_searches': [],
        'relation_saved_searches': [{
            "name": _make_relations_fixture(url, USER, PASSWORD),
        }],
        'tags': ['mytag', 'mytag2']
    }


def _make_components_fixture(url, user, passw):
    search_name = 'components'
    search = {'name': search_name,
              'search': '* topo_type=component | dedup id | sort - id | fields id, type, description, running'}
    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (url, search_name), auth=(user, passw))
    requests.post("%s/services/saved/searches" % url, data=search, auth=(user, passw)).raise_for_status()
    json_data = {"topo_type": "component", "id": "server_1", "type": "server", "description": "My important server 1"}
    requests.post("%s/services/receivers/simple" % url, json=json_data, auth=(user, passw)).raise_for_status()
    json_data = {"topo_type": "component", "id": "server_2", "type": "server", "description": "My important server 2"}
    requests.post("%s/services/receivers/simple" % url, json=json_data, auth=(user, passw)).raise_for_status()
    return search_name


def _make_relations_fixture(url, user, passw):
    search_name = 'relations'
    search = {'name': search_name,
              'search': '* topo_type=relation | dedup type, sourceId, targetId | \
fields type, sourceId, targetId, description'}
    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (url, search_name), auth=(user, passw))
    requests.post("%s/services/saved/searches" % url, data=search, auth=(user, passw)).raise_for_status()
    json_data = {"topo_type": "relation", "type": "CONNECTED", "sourceId": "server_1", "targetId": "server_2",
                 "description": "Some relation"}
    requests.post("%s/services/receivers/simple" % url, json=json_data, auth=(user, passw)).raise_for_status()
    return search_name
