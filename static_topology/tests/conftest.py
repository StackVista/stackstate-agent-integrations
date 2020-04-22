# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    return {
        'type': 'csv',
        'components_file': '/home/static_topology/components.csv',
        'relations_file': '/home/static_topology/relations.csv',
        'delimiter': ','
    }


@pytest.fixture(scope="class")
def instance(request):
    cfg = {
        'type': 'csv',
        'components_file': 'component.csv',
        'relations_file': 'relation.csv',
        'delimiter': ','
    }
    request.cls.instance = cfg
