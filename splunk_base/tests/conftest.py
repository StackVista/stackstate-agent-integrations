# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

import pytest
import requests

from stackstate_checks.dev import WaitFor, docker_run
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import SplunkInstanceConfig

from common import DISABLED_SEARCH_NAME, USER, PASSWORD, empty_instance, default_settings

HERE = os.path.dirname(os.path.abspath(__file__))


def connect_to_splunk():
    SplunkClient(SplunkInstanceConfig(empty_instance, {}, default_settings)).auth_session({})


@pytest.fixture(scope='session')
def test_environment():
    """
    Start a standalone splunk server requiring authentication.
    """
    with docker_run(
            os.path.join(HERE, 'compose', 'docker-compose.yaml'),
            conditions=[WaitFor(connect_to_splunk)],
    ):
        _make_disabled_search_fixture(empty_instance['url'], USER, PASSWORD)
        yield True


@pytest.fixture(scope='session')
def sts_environment():
    return {}


def _make_disabled_search_fixture(url, user, passw):
    search = {'name': DISABLED_SEARCH_NAME,
              'search': '* topo_type=component | dedup id | sort - id | fields id, type, description, running',
              'disabled': 1}
    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/servicesNS/nobody/search/saved/searches/%s" % (url, DISABLED_SEARCH_NAME),
                    verify=False, auth=(user, passw))
    requests.post("%s/servicesNS/nobody/search/saved/searches" % url, verify=False,
                  data=search, auth=(user, passw)).raise_for_status()
