# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    return {
        'type': 'csv',
        'health_file': '/home/static_health/health.csv',
        'delimiter': ',',
        'collection_interval': 15
    }


@pytest.fixture(scope="class")
def instance(request):
    cfg = {
        'type': 'csv',
        'health_file': 'health.csv',
        'delimiter': ',',
        'collection_interval': 15
    }
    request.cls.instance = cfg
