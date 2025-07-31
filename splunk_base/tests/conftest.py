# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

import pytest

from stackstate_checks.dev import WaitFor, docker_run
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import SplunkInstanceConfig

from common import HOST, PORT, USER, PASSWORD, empty_instance, default_settings

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
        yield True


@pytest.fixture(scope='session')
def sts_environment():
    return {}


@pytest.fixture(scope="class")
def instance(request):
    request.cls.instance = {'url': 'http://localhost'}
