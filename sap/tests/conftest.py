# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope="session")
def sts_environment():
    yield


@pytest.fixture
def instance():
    return {
        "host": "lab-sap-001",
        "url": "http://localhost",
        "user": "donadm",
        "pass": "Master01",
    }
