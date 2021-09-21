# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
from stackstate_checks.base.stubs import aggregator, topology, health

from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck
from stackstate_checks.stubs import telemetry


@pytest.fixture(scope='session')
def sts_environment():
    #  This conf instance is used when running `checksdev env start mycheck myenv`.
    #  The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    #  If you want to run an environment this object can not be empty.
    return {
        "url": "https://ton48129.live.dynatrace.com",
        "token": "some_token"
    }


@pytest.fixture(scope="class")
def instance(request):
    cfg = {
        "url": "https://ton48129.live.dynatrace.com",
        "token": "some_token"
    }
    request.cls.instance = cfg


@pytest.fixture(scope='class')
def test_instance():
    return {
        "url": "https://instance.live.dynatrace.com",
        "token": "some_token",
        "events_process_limit": 10,
        "events_boostrap_days": 5,
        "timeout": 20
    }


@pytest.fixture
def dynatrace_check(test_instance):
    check = DynatraceTopologyCheck('dynatrace', {}, {}, instances=[test_instance])
    yield check
    aggregator.reset()
    telemetry.reset()
    topology.reset()
    health.reset()
    check.commit_state(None)


def set_http_responses(requests_mock, hosts="[]", applications="[]", services="[]", processes="[]", process_groups="[]",
                       entities='{"entities": []}'):
    requests_mock.get("/api/v1/entity/infrastructure/hosts", text=hosts, status_code=200)
    requests_mock.get("/api/v1/entity/applications", text=applications, status_code=200)
    requests_mock.get("/api/v1/entity/services", text=services, status_code=200)
    requests_mock.get("/api/v1/entity/infrastructure/processes", text=processes, status_code=200)
    requests_mock.get("/api/v1/entity/infrastructure/process-groups", text=process_groups, status_code=200)
    requests_mock.get("/api/v2/entities", text=entities, status_code=200)
