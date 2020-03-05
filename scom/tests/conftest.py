# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope="session")
def sts_environment():
    return {
        "hostip": "",
        "domain": "stackstate",
        "username": "administrator",
        "password": "",
        "auth_mode": "Network",
        "streams": [
            {
                "name": "SQL",
                "class": "Microsoft.SQLServer.Generic.Presentation.ServerRolesGroup"
            }
        ]
    }


@pytest.fixture
def instance():
    return {
        "hostip": "",
        "domain": "stackstate",
        "username": "administrator",
        "password": "",
        "auth_mode": "Network",
        "streams": [
            {
                "name": "SQL",
                "class": "Microsoft.SQLServer.Generic.Presentation.ServerRolesGroup"
            }
        ]
    }
