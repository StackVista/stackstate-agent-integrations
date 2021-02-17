# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope="session")
def sts_environment():
    return {
        "host": "LAB-SAP-001",
        "url": "http://localhost",
        "user": "test",
        "pass": "test",
    }


@pytest.fixture
def instance():
    return {
        "host": "LAB-SAP-001",
        "url": "http://localhost",
        "user": "test",
        "pass": "test",
        "domain": "sap",
        "thread_count": 0,
        "environment": "sap-prod"
    }


@pytest.fixture
def https_instance():
    return {
        "host": "LAB-SAP-001",
        "url": "https://localhost",
        "user": "test",
        "pass": "test",
        "verify": False,
        "cert": "/path/to/cert.pem",
        "keyfile": "/path/to/key.pem",
        "tags": ["customer:Stackstate", "foo:bar"]
    }


@pytest.fixture
def instance_empty():
    return {
        "host": "",
        "url": "",
        "user": "",
        "pass": "",
    }
