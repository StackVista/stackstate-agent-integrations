# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import logging

from .common import HOST, PORT, USER, PASSWORD
from stackstate_checks.base.stubs import telemetry, aggregator, topology, transaction, state
from .mock import MockSplunkMetric, mock_auth_session, mock_saved_searches, mock_search, \
    mock_finalize_sid, mock_dispatch_saved_search
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigInstance, \
    SplunkConfigSavedSearch, SplunkConfig


@pytest.fixture
def get_logger():  # type: () -> logging.Logger
    return logging.getLogger('{}.{}'.format(__name__, "metric-check-name"))


@pytest.fixture
def splunk_config():  # type: () -> SplunkConfig
    splunk_config = SplunkConfig({
        'init_config': {},
        'instances': []
    })

    yield splunk_config

    telemetry.reset()
    aggregator.reset()
    topology.reset()
    transaction.reset()
    state.reset()


@pytest.fixture
def splunk_instance_config():  # type: () -> SplunkConfigInstance
    splunk_config = SplunkConfigInstance({
        'url': 'http://%s:%s' % (HOST, PORT),
        'authentication': {
            'basic_auth': {
                'username': USER,
                'password': PASSWORD
            }
        }
    })
    splunk_config.validate(partial=True)
    return splunk_config


def get_splunk_client(splunk_config, splunk_config_instance, mocks):
    # type: (SplunkConfig, SplunkConfigInstance, dict) -> MockSplunkMetric
    splunk_config.instances.append(splunk_config_instance)
    splunk_config.validate()
    splunk_client = MockSplunkMetric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, mocks)

    return splunk_client


@pytest.fixture
def splunk_metric(splunk_config, splunk_instance_config):
    # type: (SplunkConfig, SplunkConfigInstance) -> MockSplunkMetric

    splunk_instance_config.tags = ['mytag', 'mytag2']
    splunk_instance_config.saved_searches = [
        SplunkConfigSavedSearch({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    return get_splunk_client(splunk_config, splunk_instance_config, {
        'auth_session': mock_auth_session,
        'saved_searches': mock_saved_searches,
        'saved_search_results': mock_search,
        '_dispatch_saved_search': mock_dispatch_saved_search,
    })


@pytest.fixture
def splunk_config_max_query_chunk_sec_live(splunk_config, splunk_instance_config):
    # type: (SplunkConfig, SplunkConfigInstance) -> str

    splunk_instance_config.tags = ['checktag:checktagvalue']
    splunk_instance_config.saved_searches = [
        SplunkConfigSavedSearch({
            "name": "metrics",
            "parameters": {},
            'max_query_chunk_seconds': 300,
            'unique_key_fields': None
        })
    ]

    splunk_config.init_config = {
        'default_restart_history_time_seconds': 3600,
        'default_max_query_chunk_seconds': 300,
        'unique_key_fields': None
    }

    test_data = {
        "time": 0,
        "earliest_time": ""
    }

    def _mocked_current_time_seconds():
        return test_data["time"]

    def _mock_dispatch_saved_search(*args, **kwargs):
        # if test_data["earliest_time"] != "":
        #     self.assertEquals(earliest_time, test_data["earliest_time"])

        return "minimal_metrics"

    check = get_splunk_client(splunk_config, splunk_instance_config, {
        'auth_session': mock_auth_session,
        'saved_searches': mock_saved_searches,
        'saved_search_results': mock_search,
        '_dispatch_saved_search': _mock_dispatch_saved_search,
        # '_current_time_seconds': _mocked_current_time_seconds
    })
    check.check_id = "metric-check-id"
    return check.run()


@pytest.fixture
def splunk_error_response(splunk_config, splunk_instance_config):
    # type: (SplunkConfig, SplunkConfigInstance) -> MockSplunkMetric

    splunk_instance_config.tags = []
    splunk_instance_config.saved_searches = [
        SplunkConfigSavedSearch({
            "name": "error",
            "parameters": {}
        })
    ]

    return get_splunk_client(splunk_config, splunk_instance_config, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_searches': mock_saved_searches,
    })


@pytest.fixture
def splunk_minimal_metrics(splunk_config, splunk_instance_config):
    # type: (SplunkConfig, SplunkConfigInstance) -> MockSplunkMetric

    splunk_instance_config.tags = []
    splunk_instance_config.saved_searches = [
        SplunkConfigSavedSearch({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    return get_splunk_client(splunk_config, splunk_instance_config, {
        'auth_session': mock_auth_session,
        'saved_searches': mock_saved_searches,
        'saved_search_results': mock_search,
        'finalize_sid': mock_finalize_sid,
        '_dispatch_saved_search': mock_dispatch_saved_search,
    })
