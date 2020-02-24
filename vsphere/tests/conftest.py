# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope="session")
def sts_environment():
    return {
        "host": "192.168.0.106",
        "name": "vcenter-main",
        "username": "administrator@vsphere.local",
        "password": "test123"
    }


@pytest.fixture
def instance():
    return {
        "host": "192.168.0.106",
        "name": "vcenter-main",
        "username": "administrator@vsphere.local",
        "password": "test123"
    }


@pytest.fixture
def instance_empty():
    return {
        "host": "",
        "name": "",
        "username": "",
        "password": ""
    }
