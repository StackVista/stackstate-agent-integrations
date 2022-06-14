# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    return {
        "url": "http://localhost/api_jsonrpc.php",
        "user": "Admin",
        "password": "zabbix"
    }


@pytest.fixture(scope="class")
def instance(request):
    cfg = {
        "url": "http://10.0.0.1/zabbix/api_jsonrpc.php",
        "user": "Admin",
        "password": "zabbix",
        "collection_interval": 50
    }
    request.cls.instance = cfg
