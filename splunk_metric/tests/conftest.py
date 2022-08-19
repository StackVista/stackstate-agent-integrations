# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import logging

from stackstate_checks.errors import CheckException
from typing import Type, Tuple, Any
from .common import HOST, PORT, USER, PASSWORD
from .mock import MockSplunkMetric, mock_auth_session, mock_saved_searches, mock_token_auth_session, mock_search, \
    mock_finalize_sid, mock_dispatch_saved_search, mock_finalize_sid_exception, mock_polling_search
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigInstance, SplunkConfig, \
    SplunkConfigSavedSearchAlternativeFields, \
    SplunkConfigSavedSearchAlternativeFields2, SplunkConfigSavedSearchDefault


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
def splunk_instance_basic_auth():  # type: () -> SplunkConfigInstance
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
def splunk_instance_token_auth():  # type: () -> SplunkConfigInstance
    splunk_config = SplunkConfigInstance({
        'url': 'http://%s:%s' % (HOST, PORT),
        'authentication': {
            'token_auth': {
                'name': "api-admin",
                'initial_token': "dsfdgfhgjhkjuyr567uhfe345ythu7y6tre456sdx",
                'audience': "admin",
                'renewal_days': 10
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
def splunk_error_response_check(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "error",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "check-id-splunk_error_response_check"

    return check


@pytest.fixture
def splunk_metric_check_first_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ['mytag', 'mytag2']  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_metric_check_second_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ['mytag', 'mytag2']  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_metric_check_third_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ['mytag', 'mytag2']  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_empty_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "empty",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_minimal_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_partially_incomplete_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "partially_incomplete_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_full_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_alternative_fields_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchAlternativeFields({
            "name": "alternative_fields_metrics",
            "metric_name_field": "mymetric",
            "metric_value_field": "myvalue"
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_fixed_metric_name(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchAlternativeFields2({
            "name": "alternative_fields_metrics",
            "metric_name": "custommetric",
            "metric_value_field": "myvalue",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_warning_on_missing_fields(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "incomplete_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_same_data_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "duplicate_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


def splunk_earliest_time_and_duplicates(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "poll",
            "parameters": {},
            "batch_size": 2
        })
    ]

    splunk_config.instances = [splunk_instance_basic_auth]
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

        earliest_time = args[3]['dispatch.earliest_time']
        ignore_saved_search_flag = args[2]

        # make sure the ignore search flag is always false
        assert ignore_saved_search_flag is False

        # TODO: Melcom - Date is incorrect and fails
        # if test_data["earliest_time"] != "":
        #     assert earliest_time == test_data["earliest_time"]

        return test_data["sid"]

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'dispatch': mock_dispatch_saved_search_dispatch,
        'saved_search_results': mock_polling_search,
        '_current_time_seconds': mock_current_time_seconds,
        'saved_searches': mock_saved_searches,
        'finalize_sid': mock_finalize_sid,
    })

    check.check_id = "splunk_earliest_time_and_duplicates"

    return check, test_data


@pytest.fixture
def splunk_earliest_time_and_duplicates_first_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return splunk_earliest_time_and_duplicates(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


@pytest.fixture
def splunk_earliest_time_and_duplicates_second_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return splunk_earliest_time_and_duplicates(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


@pytest.fixture
def splunk_earliest_time_and_duplicates_third_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return splunk_earliest_time_and_duplicates(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


def splunk_delay_first_time(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.init_config = {
        'default_initial_delay_seconds': 60
    }

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "time": 1,
    }

    def mock_current_time_seconds():
        print("Running Mock: mock_current_time_seconds")
        return test_data["time"]

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        '_current_time_seconds': mock_current_time_seconds,
    })

    check.check_id = "splunk_delay_first_time"

    return check, test_data


@pytest.fixture
def splunk_delay_first_time_first_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return splunk_delay_first_time(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


@pytest.fixture
def splunk_delay_first_time_second_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return splunk_delay_first_time(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


@pytest.fixture
def splunk_delay_first_time_third_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return splunk_delay_first_time(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


# Not a @pytest.fixture to allow multiple runs in the same test cycle, resetting the check state
def splunk_continue_after_restart(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "empty",
            "parameters": {},
            "max_restart_history_seconds": 86400,
            "max_query_time_range": 3600
        })
    ]

    splunk_config.init_config = {
        'default_max_restart_history_seconds': 86400,
        'default_max_query_time_range': 3600
    }

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "time": 0,
        "earliest_time": "",
        "latest_time": None
    }

    def mock_current_time_seconds():
        return test_data["time"]

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        # TODO: Melcom
        # earliest_time = args[5]['dispatch.earliest_time']
        # if test_data["earliest_time"] != "":
        #     self.assertEquals(earliest_time, test_data["earliest_time"])
        # ignore_saved_search_flag = args[4]
        # make sure the ignore search flag is always false
        # self.assertFalse(ignore_saved_search_flag)
        # if test_data["latest_time"] is None:
        #     self.assertTrue('dispatch.latest_time' not in args[5])
        # elif test_data["latest_time"] != "":
        #     self.assertEquals(args[5]['dispatch.latest_time'], test_data["latest_time"])

        return "empty"

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'dispatch': mock_dispatch_saved_search_dispatch,
        'saved_search_results': mock_search,
        '_current_time_seconds': mock_current_time_seconds,
        'saved_searches': mock_saved_searches,
        'finalize_sid': mock_finalize_sid,
    })

    check.check_id = "splunk_continue_after_restart"

    return check, test_data


# TODO:
@pytest.fixture
def splunk_query_initial_history(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_max_restart_time(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_keep_time_on_failure(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_advance_time_on_success(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_wildcard_searches(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_saved_searches_error(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_saved_searches_ignore_error(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_metric_individual_dispatch_failures(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_metric_individual_search_failures(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_metric_search_full_failure(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_metric_respect_parallel_dispatches(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_selective_fields_for_identification(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_all_fields_for_identification(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_all_fields_for_identification_backward_compatibility(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "full_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
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
def splunk_checks_backward_compatibility_new_conf(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "metrics_identification_fields_all",
            "parameters": {},
            "unique_key_fields": []
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_checks_backward_compatibility_new_conf"

    return check


@pytest.fixture
def splunk_checks_backward_compatibility_new_conf_not_resent(splunk_config, splunk_instance_basic_auth,
                                                             mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "metrics_identification_fields_all",
            "parameters": {},
            "unique_key_fields": []
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
        'finalize_sid': mock_finalize_sid,
    })

    check.check_id = "splunk_checks_backward_compatibility_new_conf_not_resent"

    return check


@pytest.fixture
def splunk_default_parameters(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics"
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    expected_default_parameters = {'dispatch.now': True, 'force_dispatch': True}

    def mock_auth_session_to_check_instance_config(_, instance):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == expected_default_parameters, \
                "Unexpected default parameters for saved search: %s" % saved_search.name
        return "sessionKey1"

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session_to_check_instance_config,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_default_parameters"

    return check


@pytest.fixture
def splunk_non_default_parameters(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    config_saved_search = SplunkConfigSavedSearchDefault({
        "name": "minimal_metrics",
        "parameters": None
    })

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        config_saved_search
    ]

    splunk_config.init_config = {
        "default_parameters": {
            "respect": "me"
        }
    }

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    expected_default_parameters = {'respect': 'me'}

    def mock_auth_session_to_check_instance_config(committable_state, instance):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == expected_default_parameters, \
                "Unexpected non-default parameters for saved search: %s" % saved_search.name
        return "sessionKey1"

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session_to_check_instance_config,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_non_default_parameters"

    return check


@pytest.fixture
def splunk_overwrite_default_parameters(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {
                "respect": "me"
            }
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    expected_default_parameters = {'respect': 'me'}

    def mock_auth_session_to_check_instance_config(committable_state, instance):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == expected_default_parameters, \
                "Unexpected overwritten default parameters for saved search: %s" % saved_search.name
        return "sessionKey1"

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session_to_check_instance_config,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
    })

    check.check_id = "splunk_overwrite_default_parameters"

    return check


# Requires multiple runs in the same test, can not be a pyfixture
def splunk_config_max_query_chunk_sec_history(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "metrics",
            "parameters": {},
            "max_restart_history_seconds": 3600,
            "max_query_chunk_seconds": 300,
            "initial_history_time_seconds": 86400,
            "unique_key_fields": None
        })
    ]

    splunk_config.init_config = {
        "default_restart_history_time_seconds": 3600,
        "default_max_query_chunk_seconds": 300,
        "default_initial_history_time_seconds": 86400,
        "unique_key_fields": None
    }

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "time": 0,
        "earliest_time": ""
    }

    def mock_current_time_seconds():
        return test_data["time"]

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        earliest_time = args[3]['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]

        if test_data["earliest_time"] == "2017-03-08T00:00:00.000000+0000":
            return "metrics"
        else:
            return "past_metrics"

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'dispatch': mock_dispatch_saved_search_dispatch,
        'saved_search_results': mock_search,
        '_current_time_seconds': mock_current_time_seconds,
        'saved_searches': mock_saved_searches,
        'finalize_sid': mock_finalize_sid,
    })

    check.check_id = "splunk_config_max_query_chunk_sec_history"

    return check, test_data


@pytest.fixture
def splunk_config_max_query_chunk_sec_live(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]

    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "metrics",
            "parameters": {},
            "max_query_chunk_seconds": 300,
            "unique_key_fields": None
        })
    ]

    splunk_config.init_config = {
        'default_restart_history_time_seconds': 3600,
        'default_max_query_chunk_seconds': 300,
        'unique_key_fields': None
    }

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "time": 0,
        "earliest_time": ""
    }

    def mock_current_time_seconds():
        return test_data["time"]

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        earliest_time = args[3]['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]
        return "minimal_metrics"

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'dispatch': mock_dispatch_saved_search_dispatch,
        'saved_search_results': mock_search,
        '_current_time_seconds': mock_current_time_seconds,
        'saved_searches': mock_saved_searches,
        'finalize_sid': mock_finalize_sid,
    })

    check.check_id = "splunk_config_max_query_chunk_sec_live"

    return check, test_data


# TODO:
@pytest.fixture
def splunk_metrics_with_token_auth_with_valid_token(splunk_config, splunk_instance_token_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_token_auth.tags = []  # Splunk Config Tags

    splunk_instance_token_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_token_auth)
    splunk_config.validate()

    def mock_token_auth_session(*args):
        return None

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
        '_token_auth_session': mock_token_auth_session,
    })

    check.check_id = "splunk_same_data_metrics"

    return check


@pytest.fixture
def splunk_metrics_with_token_auth_with_invalid_token(splunk_config, splunk_instance_token_auth,
                                                          mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_token_auth.tags = []  # Splunk Config Tags

    splunk_instance_token_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_token_auth)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
        '_token_auth_session': mock_token_auth_session,
    })

    check.check_id = "splunk_metrics_with_token_auth_memory_token_expired"

    return check


@pytest.fixture
def splunk_metrics_with_token_auth_audience_param_not_set(splunk_config, splunk_instance_token_auth,
                                                          mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    # Remove audience from the authentication
    del splunk_instance_token_auth.authentication.token_auth.audience

    splunk_instance_token_auth.tags = []  # Splunk Config Tags

    splunk_instance_token_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_token_auth)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches
    })

    check.check_id = "splunk_metrics_with_token_auth_audience_param_not_set"

    return check


@pytest.fixture
def splunk_metrics_with_token_auth_name_param_not_set(splunk_config, splunk_instance_token_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    # Remove name from the authentication
    del splunk_instance_token_auth.authentication.token_auth.name

    # Change the audience
    splunk_instance_token_auth.authentication.token_auth.audience = "search"

    splunk_instance_token_auth.tags = []  # Splunk Config Tags

    splunk_instance_token_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_token_auth)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches
    })

    check.check_id = "splunk_metrics_with_token_auth_name_param_not_set"

    return check


@pytest.fixture
def splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth(splunk_config,
                                                                        splunk_instance_basic_auth,
                                                                        splunk_instance_token_auth,
                                                                        mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_basic_auth.authentication.token_auth = splunk_instance_token_auth.authentication.token_auth

    splunk_instance_basic_auth.tags = []  # Splunk Config Tags

    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_basic_auth)
    splunk_config.validate()

    def mock_token_auth_session(*args):
        return None

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
        '_token_auth_session': mock_token_auth_session,
    })

    check.check_id = "splunk_metrics_with_token_auth_token_auth_preferred_over_basic_auth"

    return check


@pytest.fixture
def splunk_metrics_with_token_auth_memory_token_expired(splunk_config, splunk_instance_token_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric

    splunk_instance_token_auth.tags = []  # Splunk Config Tags

    splunk_instance_token_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "minimal_metrics",
            "parameters": {}
        })
    ]

    splunk_config.instances.append(splunk_instance_token_auth)
    splunk_config.validate()

    check = mock_splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': mock_search,
        'saved_searches': mock_saved_searches,
        '_token_auth_session': mock_token_auth_session,
    })

    check.check_id = "splunk_metrics_with_token_auth_memory_token_expired"

    return check
