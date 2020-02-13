# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    return {
        'hostip': '34.244.241.169',
        'domain': 'stackstate',
        'username': 'administrator',
        'password': '7hVlj5lVGZw3NqSIIa6zbvU)A=3GuaZX',
        'auth_mode': 'Network',
        'streams':[
        {'name': 'SQL',
        'class': 'Microsoft.SQLServer.Generic.Presentation.ServerRolesGroup'    }
        ]
    }


@pytest.fixture
def instance():
    return {
        'hostip': '34.244.241.169',
        'domain': 'stackstate',
        'username': 'administrator',
        'password': '7hVlj5lVGZw3NqSIIa6zbvU)A=3GuaZX',
        'auth_mode': 'Network',
        'streams':[
        {'name': 'SQL',
        'class': 'Microsoft.SQLServer.Generic.Presentation.ServerRolesGroup'    }
        ]
    }
