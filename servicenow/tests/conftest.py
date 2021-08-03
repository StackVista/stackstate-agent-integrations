# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
from stackstate_checks.stubs import aggregator, telemetry, topology

from stackstate_checks.servicenow import ServicenowCheck


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
def test_cr_instance():
    return {
        "url": "https://instance.service-now.com",
        "user": "some_user",
        "password": "secret",
        "batch_size": 100,
        # 'planned_change_request_resend_schedule': 1,
        # 'custom_planned_start_date_field': 'u_custom_start_date'
        # 'custom_planned_end_date_field': 'u_custom_end_date'
    }


@pytest.fixture
def servicenow_check(test_cr_instance):
    check = ServicenowCheck('servicenow', {}, instances=[test_cr_instance])
    yield check
    aggregator.reset()
    telemetry.reset()
    topology.reset()
    check.commit_state(None)
