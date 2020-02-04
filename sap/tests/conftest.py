# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope="session")
def sts_environment():
    return {
        "host": "LAB-SAP-001",
        "url": "http://localhost",
        "user": "donadm",
        "pass": "Master01",
    }


@pytest.fixture
def instance():
    return {
        "host": "LAB-SAP-001",
        "url": "http://localhost",
        "user": "donadm",
        "pass": "Master01",
    }


@pytest.fixture
def instance_empty():
    return {
        "host": "",
        "url": "",
        "user": "",
        "pass": "",
    }
