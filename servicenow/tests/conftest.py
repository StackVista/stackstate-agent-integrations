# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest

from stackstate_checks.servicenow.client import ServiceNowClient
from stackstate_checks.stubs import aggregator, telemetry, topology

from stackstate_checks.servicenow import ServiceNowCheck


@pytest.fixture(scope='session')
def sts_environment():
    """
    This conf instance is used when running `checksdev env start mycheck myenv`.
    The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    If you want to run an environment this object can not be empty.
    """
    return {
        "url": "https://instance.service-now.com",
        "user": "some_user",
        "password": "secret",
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


@pytest.fixture(scope="class")
def test_instance():
    return {
        "url": "https://instance.service-now.com",
        "user": "some_user",
        "password": "secret",
        "batch_size": 100,
    }


@pytest.fixture
def servicenow_check(test_instance):
    check = ServiceNowCheck('servicenow', {}, instances=[test_instance])
    yield check
    aggregator.reset()
    telemetry.reset()
    topology.reset()
    check.commit_state(None)


@pytest.fixture
def test_client(test_instance):
    check = ServiceNowCheck('servicenow', {}, instance=[test_instance])
    test_instance_schema = check._get_instance_schema(test_instance)
    client = ServiceNowClient(test_instance_schema)
    return client


@pytest.fixture
def get_url_auth(test_instance):
    url = "{}/api/now/table/cmdb_ci".format(test_instance.get('url'))
    auth = (test_instance.get('user'), test_instance.get('password'))
    return url, auth
