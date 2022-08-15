# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import logging
import json

from stackstate_checks.errors import CheckException
from typing import Type
from .common import HOST, PORT, USER, PASSWORD
from .mock import MockSplunkMetric, mock_auth_session, mock_saved_searches, mock_search, \
    mock_finalize_sid, mock_dispatch_saved_search, mock_finalize_sid_exception, mock_polling_search
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigInstance, \
    SplunkConfigSavedSearch, SplunkConfig, SplunkConfigSavedSearchAlternativeFields, \
    SplunkConfigSavedSearchAlternativeFields2, SplunkConfigSavedSearchWithBatch


@pytest.fixture
def get_logger():  # type: () -> logging.Logger
    return logging.getLogger('{}.{}'.format(__name__, "metric-check-name"))


@pytest.fixture
def splunk_config():  # type: () -> SplunkConfig
    splunk_config = SplunkConfig({
        'init_config': {},
        'instances': []
    })

    return splunk_config


@pytest.fixture
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

    check.check_id = "check-id-splunk_error_response_check"

    return check


@pytest.fixture
def splunk_metric_check_first_run(splunk_config, splunk_instance, mock_splunk_metric):
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

    check.check_id = "splunk_metric_check"

    return check


@pytest.fixture
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
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
        'finalize_sid': mock_finalize_sid,
    })

    check.check_id = "splunk_metric_check"

    return check


@pytest.fixture
def splunk_metric_check_third_run(splunk_config, splunk_instance, mock_splunk_metric):
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
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'finalize_sid': mock_finalize_sid_exception,
    })

    check.check_id = "splunk_metric_check"

    return check


@pytest.fixture
def splunk_empty_metrics(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = []  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "empty",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_empty_metrics"

    return check


@pytest.fixture
def splunk_minimal_metrics(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = []  # Splunk Config Tags

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
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_minimal_metrics"

    return check


@pytest.fixture
def splunk_partially_incomplete_metrics(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = []  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "partially_incomplete_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_partially_incomplete_metrics"

    return check


@pytest.fixture
def splunk_full_metrics(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_full_metrics"

    return check


@pytest.fixture
def splunk_alternative_fields_metrics(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = []  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchAlternativeFields({
            "name": "alternative_fields_metrics",
            "metric_name_field": "mymetric",
            "metric_value_field": "myvalue",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_alternative_fields_metrics"

    return check


@pytest.fixture
def splunk_fixed_metric_name(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = []  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchAlternativeFields2({
            "name": "alternative_fields_metrics",
            "metric_name": "custommetric",
            "metric_value_field": "myvalue",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_fixed_metric_name"

    return check


@pytest.fixture
def splunk_warning_on_missing_fields(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = []  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "incomplete_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_warning_on_missing_fields"

    return check


# TODO
@pytest.fixture
def splunk_same_data_metrics(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = []  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "duplicate_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


@pytest.fixture
def splunk_earliest_time_and_duplicates(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchWithBatch({
            "name": "poll",
            "parameters": {},
            "batch_size": 2
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "expected_searches": ["poll"],
        "sid": "",
        "time": 0,
        "earliest_time": "",
        "throw": False
    }

    def mock_current_time_seconds():
        print("Running Mock: mock_current_time_seconds")

        return test_data["time"]

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        print("Running Mock: mock_dispatch_saved_search_dispatch")

        if test_data["throw"]:
            raise CheckException("Is broke it")

        earliest_time = args[5]['dispatch.earliest_time']

        ignore_saved_search_flag = args[4]

        # # make sure the ignore search flag is always false
        # self.assertFalse(ignore_saved_search_flag)
        # if test_data["earliest_time"] != "":
        #     self.assertEquals(earliest_time, test_data["earliest_time"])

        return test_data["sid"]

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'dispatch': mock_dispatch_saved_search_dispatch,
        'saved_search_results': mock_polling_search,
        'current_time_seconds': mock_current_time_seconds,
        'saved_searches': mock_saved_searches,
        'finalize_sid': mock_finalize_sid,
    })

    check.check_id = "splunk_earliest_time_and_duplicates"

    return check


@pytest.fixture
def splunk_delay_first_time(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_continue_after_restart(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_query_initial_history(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_max_restart_time(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_keep_time_on_failure(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_advance_time_on_success(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_wildcard_searches(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_saved_searches_error(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_saved_searches_ignore_error(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metric_individual_dispatch_failures(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metric_individual_search_failures(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metric_search_full_failure(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metric_respect_parallel_dispatches(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_selective_fields_for_identification(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_all_fields_for_identification(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_all_fields_for_identification_backward_compatibility(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_all_fields_for_identification_backward_compatibility_new_conf(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_default_parameters(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_non_default_parameters(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_overwrite_default_parameters(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_config_max_query_chunk_sec_history(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_config_max_query_chunk_sec_live(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metrics_with_token_auth_with_valid_token(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metrics_with_token_auth_with_invalid_token(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metrics_with_token_auth_audience_param_not_set(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metrics_with_token_auth_name_param_not_set(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


# TODO:
@pytest.fixture
def splunk_metrics_with_token_auth_memory_token_expired(splunk_config, splunk_instance, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearch({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check
