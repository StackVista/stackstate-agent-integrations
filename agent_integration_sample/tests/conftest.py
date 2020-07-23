# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    return {}


@pytest.fixture(scope="class")
def instance(request):
    request.cls.instance = {'url': 'http://localhost'}
