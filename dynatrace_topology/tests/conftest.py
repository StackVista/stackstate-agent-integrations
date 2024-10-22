# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json

import pytest

from stackstate_checks.dynatrace_topology import DynatraceTopologyCheck


@pytest.fixture(scope='session')
def sts_environment():
    #  This conf instance is used when running `checksdev env start mycheck myenv`.
    #  The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    #  If you want to run an environment this object can not be empty.
    return {
        "url": "https://ton48129.live.dynatrace.com",
        "token": "some_token",
        'collection_interval': 15
    }


@pytest.fixture(scope='class')
def test_instance():
    return {
        "url": "https://instance.live.dynatrace.com",
        "token": "some_token",
        "timeout": 20,
        'collection_interval': 15
    }


@pytest.fixture(scope='class')
def test_instance_relative_time():
    return {
        "url": "https://instance.live.dynatrace.com",
        "token": "some_token",
        "relative_time": "day",
        'collection_interval': 15
    }


@pytest.fixture
def dynatrace_check(test_instance, aggregator, telemetry, topology, health):
    check = DynatraceTopologyCheck('dynatrace', {}, {}, instances=[test_instance])
    yield check
    aggregator.reset()
    telemetry.reset()
    topology.reset()
    health.reset()
    check.commit_state(None)


def set_http_responses(requests_mock, hosts="[]", applications="[]", services="[]", processes="[]", process_groups="[]",
                       entities='{"entities": []}', monitors='{"monitors": []}'):
    requests_mock.get("/api/v1/entity/infrastructure/hosts", text=hosts, status_code=200)
    requests_mock.get("/api/v1/entity/applications", text=applications, status_code=200)
    requests_mock.get("/api/v2/entities?entitySelector=type%28%22SERVICE%22%29&from=now-hour&fields=%2BfromRelationships%2C%2BtoRelationships%2C%2Btags%2C%2BmanagementZones%2C%2Bproperties", text=services, status_code=200)
    requests_mock.get("/api/v1/entity/infrastructure/processes", text=processes, status_code=200)
    requests_mock.get("/api/v1/entity/infrastructure/process-groups", text=process_groups, status_code=200)
    requests_mock.get("/api/v2/entities", text=entities, status_code=200)
    requests_mock.get("/api/v1/synthetic/monitors", text=monitors, status_code=200)


def sort_topology_data(topology_instance):
    """
    Sort the keys of components and relations, so we can actually match it
    :param topology_instance: dictionary
    :return: list of components, list of relations
    """
    components = [json.dumps(component, sort_keys=True) for component in topology_instance["components"]]
    relations = [json.dumps(relation, sort_keys=True) for relation in topology_instance["relations"]]
    return components, relations


def assert_topology(expected_topology, test_topology):
    """
    Sort the keys of components and relations, so we can actually match it
    :param expected_topology: expected topology read from file
    :param test_topology: topology gathered during test
    :return: None
    """
    components, relations = sort_topology_data(test_topology)
    expected_components, expected_relations = sort_topology_data(expected_topology)
    assert components == expected_components
    assert len(relations) == len(expected_relations)
    for relation in relations:
        assert relation in expected_relations
