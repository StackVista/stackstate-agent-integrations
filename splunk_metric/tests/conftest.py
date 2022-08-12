# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import logging

from typing import Type, Tuple
from .common import HOST, PORT, USER, PASSWORD
from .mock import MockSplunkMetric, mock_auth_session, mock_saved_searches, mock_search, \
    mock_finalize_sid, mock_dispatch_saved_search
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigInstance, \
    SplunkConfigSavedSearch, SplunkConfig


@pytest.fixture(scope="session")
def get_logger():  # type: () -> logging.Logger
    return logging.getLogger('{}.{}'.format(__name__, "metric-check-name"))


@pytest.fixture(scope="class")
def splunk_config():  # type: () -> SplunkConfig
    splunk_config = SplunkConfig({
        'init_config': {},
        'instances': []
    })

    return splunk_config


@pytest.fixture(scope="class")
def splunk_instance():  # type: () -> SplunkConfigInstance
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


@pytest.fixture
def mock_splunk_metric(telemetry, aggregator, topology, transaction, state):
    # type: (any, any, any, any, any) -> Type[MockSplunkMetric]

    # Bring back the splunk mock metrics
    yield MockSplunkMetric

    # Clean the singleton states that could have been used
    telemetry.reset()
    aggregator.reset()
    topology.reset()
    transaction.reset()
    state.reset()


@pytest.fixture
def splunk_error_response_check(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = []  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "error",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_searches': mock_saved_searches,
    })

    return check


@pytest.fixture(scope="function")
def splunk_metric_check(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ['mytag', 'mytag2']  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'saved_searches': mock_saved_searches,
        'saved_search_results': mock_search,
        '_dispatch_saved_search': mock_dispatch_saved_search,
    })

    return check


@pytest.fixture(scope="function")
def splunk_metric_check_second_run(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ['mytag', 'mytag2']  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'saved_searches': mock_saved_searches,
        'saved_search_results': mock_search,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'finalize_sid': mock_finalize_sid,
    })

    return check
