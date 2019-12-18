# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    yield


@pytest.fixture
def instance():
    return {
        'url': 'http://localhost:7180',
        'username': 'cloudera',
        'password': 'password',
        'api_version': 'v18'
    }
