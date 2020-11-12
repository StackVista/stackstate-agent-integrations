# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    """
    This conf instance is used when running `checksdev env start mycheck myenv`.
    The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    If you want to run an environment this object can not be empty.
    """
    return {
        "url": "https://dev66356.service-now.com",
        "user": "admin",
        "password": "Stackstate@123",
        "batch_size": 100,
        "include_resource_types": [
            "cmdb_ci_netgear",
            "cmdb_ci_win_cluster",
            "cmdb_ci_win_cluster_node",
            "cmdb_ci_app_server_java"
        ]
    }


@pytest.fixture(scope="class")
def instance(request):
    cfg = {
        "url": "https://instance.service-now.com",
        "user": "some_user",
        "password": "secret",
        "batch_size": 100,
        "include_resource_types": ["cmdb_ci_netgear", "cmdb_ci_cluster", "cmdb_ci_app_server"]
    }
    request.cls.instance = cfg
