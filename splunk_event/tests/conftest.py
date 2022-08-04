# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


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
def saved_searches_error(instance):
    instance['saved_searches'] = [{
        "name": "error",
        "parameters": {}
    }]
