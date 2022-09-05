# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import os
from typing import Dict, Generator, List

import pytest
import requests
from requests_mock import Mocker

from stackstate_checks.base.stubs.aggregator import AggregatorStub
from stackstate_checks.base.stubs.state import StateStub
from stackstate_checks.base.stubs.transaction import TransactionStub
from stackstate_checks.base.utils.common import read_file
from stackstate_checks.dev import docker_run, WaitFor
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import SplunkInstanceConfig
from stackstate_checks.splunk_event import SplunkEvent
from stackstate_checks.splunk_event.splunk_event import default_settings
from .common import HOST, PORT, USER, PASSWORD

# unit test constants
UNIT_TEST_URL = "http://localhost:8089"
SID = "admin__admin__search__RMD567222de41fbb54c3_at_1660747475_3"
SAVED_SEARCH = "test_events"


def _connect_to_splunk():
    # type: () -> None
    SplunkClient(
        SplunkInstanceConfig(
            {
                'url': 'http://%s:%s' % (HOST, PORT),
                'authentication': {
                    'basic_auth': {
                        'username': USER,
                        'password': PASSWORD
                    },
                },
                'saved_searches': [],
                'collection_interval': 15
            },
            {},
            default_settings
        )
    ).auth_session({})


@pytest.fixture(scope='session')
def test_environment():
    # type: () -> Generator
    """
    Start a standalone splunk server requiring authentication.
    """
    with docker_run(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compose', 'docker-compose.yaml'),
            conditions=[WaitFor(_connect_to_splunk)],
    ):
        yield True


# this fixture is used for checksdev env start
@pytest.fixture(scope='session')
def sts_environment(test_environment):
    # type: (Generator) -> Dict
    """
    This fixture is used for checksdev env start.
    """
    url = 'http://%s:%s' % (HOST, PORT)
    yield {
        'url': url,
        'authentication': {
            'basic_auth': {
                'username': USER,
                'password': PASSWORD
            },
        },
        'saved_searches': [{
            "name": _make_event_fixture(url, USER, PASSWORD),
        }],
        'collection_interval': 15
    }


@pytest.fixture
def integration_test_instance():
    # type: () -> Dict
    url = 'http://%s:%s' % (HOST, PORT)
    return {
        'url': url,
        'authentication': {
            'basic_auth': {
                'username': USER,
                'password': PASSWORD
            },
        },
        'saved_searches': [{
            "name": _make_event_fixture(url, USER, PASSWORD),
        }],
        'collection_interval': 15
    }


def _make_event_fixture(url, user, password):
    # type: (str, str, str) -> str
    """
    Send requests to a Splunk instance for creating `test_events` search.
    The Splunk started with Docker Compose command when we run integration tests.
    """
    search_name = 'test_events'
    source_type = "sts_test_data"

    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (url, search_name), auth=(user, password))

    requests.post("%s/services/saved/searches" % url,
                  data={"name": search_name,
                        "search": 'sourcetype="sts_test_data" '
                                  '| eval status = upper(status) '
                                  '| search status=critical OR status=error OR status=warning OR status=ok '
                                  '| table _time _bkt _cd host status description'},
                  auth=(user, password)).raise_for_status()
    requests.post("%s/services/receivers/simple" % url,
                  params={"host": "host01", "sourcetype": source_type},
                  json={"status": "OK", "description": "host01 test ok event"},
                  auth=(user, password)).raise_for_status()
    requests.post("%s/services/receivers/simple" % url,
                  params={"host": "host02", "sourcetype": source_type},
                  json={"status": "CRITICAL", "description": "host02 test critical event"},
                  auth=(user, password)).raise_for_status(),
    requests.post("%s/services/receivers/simple" % url,
                  params={"host": "host03", "sourcetype": source_type},
                  json={"status": "error", "description": "host03 test error event"},
                  auth=(user, password)).raise_for_status(),
    requests.post("%s/services/receivers/simple" % url,
                  params={"host": "host04", "sourcetype": source_type},
                  json={"status": "warning", "description": "host04 test warning event"},
                  auth=(user, password)).raise_for_status()

    return search_name


@pytest.fixture
def splunk_event_check(unit_test_instance, unit_test_config, aggregator, state, transaction):
    # type: (Dict, Dict, AggregatorStub, StateStub, TransactionStub) -> SplunkEvent
    check = SplunkEvent("splunk", unit_test_config, {}, [unit_test_instance])
    check.check_id = "splunk_test_id"
    yield check
    aggregator.reset()
    state.reset()
    transaction.reset()


@pytest.fixture
def unit_test_instance():
    # type: () -> Dict
    return {
        "url": UNIT_TEST_URL,
        "authentication": {
            "basic_auth": {
                "username": "admin",
                "password": "admin12345"
            }
        },
        "saved_searches": [
            {
                "name": "test_events",
                "parameters": {},
            }
        ],
        "tags": []
    }


@pytest.fixture
def unit_test_config():
    # type: () -> Dict
    return {}


@pytest.fixture
def batch_size_2(unit_test_instance):
    # type: (Dict) -> None
    unit_test_instance["saved_searches"][0]["batch_size"] = 2


@pytest.fixture
def initial_delay_60_seconds(unit_test_config):
    # type: (Dict) -> None
    unit_test_config["default_initial_delay_seconds"] = 60


@pytest.fixture
def initial_history_86400(unit_test_config, unit_test_instance):
    # type: (Dict, Dict) -> None
    unit_test_config["default_initial_history_time_seconds"] = 86400
    unit_test_config["default_max_query_chunk_seconds"] = 3600
    unit_test_instance["saved_searches"][0]["max_initial_history_seconds"] = 86400
    unit_test_instance["saved_searches"][0]["max_query_chunk_seconds"] = 3600


@pytest.fixture
def restart_history_86400(unit_test_config, unit_test_instance):
    # type: (Dict, Dict) -> None
    unit_test_config["default_max_restart_history_seconds"] = 86400
    unit_test_config["default_max_query_time_range"] = 3600
    unit_test_instance["saved_searches"][0]["max_restart_history_seconds"] = 86400
    unit_test_instance["saved_searches"][0]["max_query_time_range"] = 3600


@pytest.fixture
def max_restart_time(unit_test_config, unit_test_instance):
    # type: (Dict, Dict) -> None
    unit_test_config["default_restart_history_time_seconds"] = 3600
    unit_test_config["default_max_query_chunk_seconds"] = 3600
    unit_test_instance["saved_searches"][0]["max_restart_history_seconds"] = 3600
    unit_test_instance["saved_searches"][0]["max_query_chunk_seconds"] = 3600


@pytest.fixture
def wildcard_saved_search(unit_test_instance):
    # type: (Dict) -> None
    unit_test_instance["saved_searches"][0]["match"] = "test_even*"
    del unit_test_instance["saved_searches"][0]["name"]


@pytest.fixture
def ignore_saved_search_errors(unit_test_instance):
    unit_test_instance["ignore_saved_search_errors"] = True


@pytest.fixture
def multiple_saved_searches(unit_test_instance):
    unit_test_instance["saved_searches_parallel"] = 2
    unit_test_instance["saved_searches"] = [
        {"name": "savedsearch1", "parameters": {}},
        {"name": "savedsearch2", "parameters": {}},
        {"name": "savedsearch3", "parameters": {}},
        {"name": "savedsearch4", "parameters": {}},
        {"name": "savedsearch5", "parameters": {}}
    ]


@pytest.fixture
def selective_events(unit_test_instance):
    unit_test_instance["saved_searches"][0]["unique_key_fields"] = ["uid1", "uid2"]


def extract_title_and_type_from_event(event):
    # type: (Dict) -> Dict
    """Extracts event title and type. Method call aggregator.assert_event needs event fields as **kwargs parameter."""
    return {"msg_title": event["msg_title"], "event_type": event["event_type"]}


def common_requests_mocks(requests_mock):
    # type: (Mocker) -> None
    """
    Splunk client request flow: Basic authentication > List saved searches > Dispatch search > Get search results
    Here we mock first three requests.
    """
    basic_auth_mock(requests_mock)
    list_saved_searches_mock(requests_mock)
    dispatch_search_mock(requests_mock)


def dispatch_search_mock(requests_mock, search=SAVED_SEARCH, sid=SID, url=UNIT_TEST_URL):
    # type: (Mocker, str, str, str) -> None
    """
    Dispatch search and get job's sid.
    """
    requests_mock.post(
        url="{}/servicesNS/admin/search/saved/searches/{}/dispatch".format(url, search),
        status_code=201,
        text=json.dumps({"sid": sid})
    )


def list_saved_searches_mock(requests_mock, search_results=None, url=UNIT_TEST_URL):
    # type: (Mocker, List[str], str) -> None
    """
    List saved searches.
    """
    entry = []
    if not search_results:
        search_results = [SAVED_SEARCH]
    for search_result in search_results:
        entry.append({"name": search_result})

    requests_mock.get(
        url="{}/services/saved/searches?output_mode=json&count=-1".format(url),
        status_code=200,
        text=json.dumps(
            {"entry": entry,
             "paging": {"total": len(entry), "perPage": 18446744073709552000, "offset": 0},
             "messages": []}
        )
    )


def basic_auth_mock(requests_mock, url=UNIT_TEST_URL):
    # type: (Mocker, str) -> None
    """
    Basic authentication.
    """
    requests_mock.post(
        url="{}/services/auth/login?output_mode=json".format(url),
        status_code=200,
        text='{"sessionKey": "testSessionKey123", "message": "", "code": ""}'
    )


def job_results_mock(requests_mock, response_file, sid=SID, offset=0, count=1000, url=UNIT_TEST_URL):
    # type: (Mocker, str, str, int, int, str) -> None
    """
    Request for getting job result.
    """
    job_results_path = "{}/servicesNS/-/-/search/jobs/{}/results?output_mode=json&offset={}&count={}".format(url,
                                                                                                             sid,
                                                                                                             offset,
                                                                                                             count)
    requests_mock.get(url=job_results_path, status_code=200, text=read_file(response_file, "ci/fixtures"))


def search_job_finalized_mock(requests_mock, sid=SID, url=UNIT_TEST_URL):
    # type: (Mocker, str, str) -> None
    """
    Finalize search job.
    """
    requests_mock.post(
        url="{}/services/search/jobs/{}/control?output_mode=json".format(url, sid),
        status_code=200,
        text='{"messages":[{"type":"INFO","text":"Search job finalized."}]}'
    )


def batch_job_results_mock(requests_mock, response_files, batch_size, sid=SID, url=UNIT_TEST_URL):
    # type: (Mocker, List, int, str, str) -> None
    """
    Iterates through response files list and sets up requests_mock for each.
    """
    for i, response_file in enumerate(response_files):
        job_results_mock(requests_mock, response_file, offset=i * batch_size, count=batch_size, sid=sid, url=url)


def saved_searches_error_mock(requests_mock, url=UNIT_TEST_URL):
    # type: (Mocker, str) -> None
    """
    Explode with 400 when listing saved searches.
    """
    requests_mock.get(
        url="{}/services/saved/searches?output_mode=json&count=-1".format(url),
        status_code=400,
        text='{"messages":[{"type":"ERROR","text":"Error raised for testing!"}]}',
        reason="Mocked error for unit test!"
    )


def dispatch_search_error_mock(requests_mock, search=SAVED_SEARCH, url=UNIT_TEST_URL):
    # type: (Mocker, str, str) -> None
    """
    Explode with 400 when trying to dispatch search.
    """
    requests_mock.post(
        url=("{}/servicesNS/admin/search/saved/searches/{}/dispatch".format(url, search)),
        status_code=400,
        text='{"messages":[{"type":"ERROR","text":"Error raised for testing!"}]}',
        reason="Mocked error for unit test!"
    )
