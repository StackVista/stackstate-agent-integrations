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
        'host': 'ec2-34-244-15-117.eu-west-1.compute.amazonaws.com',
        'port': '7180',
        'username': 'cloudera',
        'password': 'v4APBoEqW4',
        'api_version': 'v18',
        'verify_ssl': 'False'
    }
