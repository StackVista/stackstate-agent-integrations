# (C) Datadog, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    return {
        "url": "capital-one-aws-accounts"
    }


@pytest.fixture
def instance():
    return {
        "url": "capital-one-aws-accounts"
    }


@pytest.fixture
def file_instance():
    return {
        "url": "./tests/data/sample_data.txt"
    }
