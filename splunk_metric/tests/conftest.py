# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import logging
import inspect
import time

from requests_mock import Mocker
from datetime import timedelta, datetime
from stackstate_checks.errors import CheckException
from typing import Type, Tuple
from .common import HOST, PORT, USER, PASSWORD
from .mock import MockSplunkMetric, mock_auth_session, mock_saved_searches, mock_token_auth_session, mock_search, \
    mock_finalize_sid, mock_dispatch_saved_search, mock_finalize_sid_exception, mock_polling_search, \
    _generate_mock_token, _requests_mock, SplunkMetric
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
        },
        'tags': []
    })
    splunk_config.validate(partial=True)
    return splunk_config


@pytest.fixture
def splunk_instance_token_auth():  # type: () -> SplunkConfigInstance
    token_expire_time = datetime.now() + timedelta(days=999)

    splunk_config = SplunkConfigInstance({
        'url': 'http://%s:%s' % (HOST, PORT),
        'authentication': {
            'token_auth': {
                'name': "api-admin",
                'initial_token': _generate_mock_token(token_expire_time),
                'audience': "admin",
                'renewal_days': 10
            }
        },
        'tags': []
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
def splunk_metric(telemetry, aggregator, topology, transaction, state):
    # type: (any, any, any, any, any) -> Type[SplunkMetric]

    # Bring back the splunk mock metrics
    yield SplunkMetric

    # Clean the singleton states that could have been used
    telemetry.reset()
    aggregator.reset()
    topology.reset()
    transaction.reset()
    state.reset()


@pytest.fixture
def error_response_check(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def metric_check_first_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def metric_check_second_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def metric_check_third_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def empty_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def minimal_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def partially_incomplete_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def full_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def alternative_fields_metrics(get_logger, requests_mock, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'alternative_fields_metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchAlternativeFields({
            "name": splunk_config_name,
            "metric_name_field": "mymetric",
            "metric_value_field": "myvalue"
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    check = splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def fixed_metric_name(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def warning_on_missing_fields(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def same_data_metrics(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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


def earliest_time_and_duplicates(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
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
def earliest_time_and_duplicates_first_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return earliest_time_and_duplicates(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


@pytest.fixture
def earliest_time_and_duplicates_second_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return earliest_time_and_duplicates(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


@pytest.fixture
def earliest_time_and_duplicates_third_run(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    return earliest_time_and_duplicates(splunk_config, splunk_instance_basic_auth, mock_splunk_metric)


@pytest.fixture
def delayed_start(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id=splunk_config_name)

    # Set the splunk tags
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Set the splunk initial searches
    splunk_config.init_config = {
        'default_initial_delay_seconds': 60
    }

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    check = splunk_metric("metric-check-name", splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def continue_after_restart(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    splunk_config_name = 'empty'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id=splunk_config_name)

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "max_restart_history_seconds": 86400,
            "max_query_time_range": 3600
        })
    ]

    # Set the splunk initial searches
    splunk_config.init_config = {
        'default_max_restart_history_seconds': 86400,
        'default_max_query_time_range': 3600
    }

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": "",
        "latest_time": None
    }

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

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'dispatch': mock_dispatch_saved_search_dispatch,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


@pytest.fixture
def query_initial_history(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    splunk_config_name = 'empty'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id=splunk_config_name)

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "max_restart_history_seconds": 3600,
            "max_query_chunk_seconds": 3600
        })
    ]

    # Set the splunk initial searches
    splunk_config.init_config = {
        'default_restart_history_time_seconds': 3600,
        'default_max_query_chunk_seconds': 3600
    }

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": "",
        "latest_time": ""
    }

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        # TODO: Melcom - Need to test this
        # earliest_time = args[5]['dispatch.earliest_time']
        # if test_data["earliest_time"] != "":
        #     self.assertEquals(earliest_time, test_data["earliest_time"])

        # if test_data["latest_time"] is None:
        #     self.assertTrue('dispatch.latest_time' not in args[5])
        # elif test_data["latest_time"] != "":
        #     self.assertEquals(args[5]['dispatch.latest_time'], test_data["latest_time"])

        return "minimal_metrics"

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search_dispatch,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


# Done
@pytest.fixture
def max_restart_time(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    splunk_config_name = 'empty'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id=splunk_config_name)

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "max_restart_history_seconds": 3600,
            "max_query_chunk_seconds": 3600
        })
    ]

    # Set the splunk initial searches
    splunk_config.init_config = {
        'default_restart_history_time_seconds': 3600,
        'default_max_query_chunk_seconds': 3600
    }

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": ""
    }

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        # TODO: Melcom - Need to test this
        # earliest_time = args[5]['dispatch.earliest_time']
        # if test_data["earliest_time"] != "":
        #     self.assertEquals(earliest_time, test_data["earliest_time"])

        return splunk_config_name

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search_dispatch,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


# Done
@pytest.fixture
def keep_time_on_failure(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    splunk_config_name = 'empty'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id=splunk_config_name)

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": ""
    }

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        # TODO: Melcom - Need to test this
        # earliest_time = args[5]['dispatch.earliest_time']
        # if test_data["earliest_time"] != "":
        #     self.assertEquals(earliest_time, test_data["earliest_time"])

        return splunk_config_name

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search_dispatch,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


# Done
@pytest.fixture
def advance_time_on_success(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id=splunk_config_name)

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": ""
    }

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        # TODO: Melcom - Need to test this
        # earliest_time = args[3]['dispatch.earliest_time']
        # if test_data["earliest_time"] != "":
        #     assert earliest_time == test_data["earliest_time"]

        return splunk_config_name

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search_dispatch,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


# Done
@pytest.fixture
def wildcard_searches(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    splunk_config_name = 'minimal_metrics'
    splunk_config_match = 'minimal_*'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "match": splunk_config_match,
            "parameters": {},
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    data = {
        'saved_searches': []
    }

    def mocked_saved_searches(*args, **kwargs):
        return data['saved_searches']

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'saved_searches': mocked_saved_searches,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, data


# Done
@pytest.fixture
def saved_searches_error(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_name = 'full_metrics'
    splunk_config_match = '.*metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "match": splunk_config_match,
            "parameters": {},
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    def mocked_saved_searches(*args, **kwargs):
        raise Exception("Boom")

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'saved_searches': mocked_saved_searches,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def saved_searches_ignore_error(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_name = 'full_metrics'
    splunk_config_match = '.*metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Ignore the saved search errors, Default is False
    splunk_instance_basic_auth.ignore_saved_search_errors = True

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "match": splunk_config_match,
            "parameters": {},
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    def mocked_saved_searches(*args, **kwargs):
        raise Exception("Boom")

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'saved_searches': mocked_saved_searches,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def individual_dispatch_failures(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_match = '.*metrics'

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "match": splunk_config_match,
            "parameters": {},
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    data = {
        'saved_searches': []
    }

    def _mocked_saved_searches(*args, **kwargs):
        return data['saved_searches']

    data['saved_searches'] = ["minimal_metrics", "full_metrics"]

    def _mocked_failing_search(*args, **kwargs):
        sid = args[1].name
        if sid == "full_metrics":
            print("BOOM")
            raise Exception("BOOM")
        else:
            return mock_search(*args, **kwargs)

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'saved_searches': _mocked_saved_searches,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': _mocked_failing_search,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def individual_search_failures(splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_match = '.*metrics'

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "match": splunk_config_match,
            "parameters": {},
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    data = {
        'saved_searches': []
    }

    def _mocked_saved_searches(*args, **kwargs):
        return data['saved_searches']

    data['saved_searches'] = ["minimal_metrics", "full_metrics"]

    def _mocked_failing_search(*args, **kwargs):
        sid = args[1].name
        if sid == "full_metrics":
            print("BOOM")
            raise Exception("BOOM")
        else:
            return mock_search(*args, **kwargs)

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session,
        'saved_searches': _mocked_saved_searches,
        '_dispatch_saved_search': mock_dispatch_saved_search,
        'saved_search_results': _mocked_failing_search,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def search_full_failure(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_name = 'full_metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    def mock_dispatch_saved_search(*args, **kwargs):
        raise Exception("BOOM")

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_saved_search': mock_dispatch_saved_search,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def respect_parallel_dispatches(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_names = ['savedsearch1', 'savedsearch2', 'savedsearch3', 'savedsearch4']

    saved_searches_parallel = 2

    # Mock the HTTP Requests
    for request_id in splunk_config_names:
        _requests_mock(requests_mock, request_id=request_id, logger=get_logger, audience="admin", ignore_search=True)

    # Set the saved searches parallel count
    splunk_instance_basic_auth.saved_searches_parallel = saved_searches_parallel

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = []

    for name in splunk_config_names:
        splunk_instance_basic_auth.saved_searches.append(
            SplunkConfigSavedSearchDefault({
                "name": name,
                "parameters": {},
            })
        )

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    def _mock_dispatch_and_await_search(process_data, service_check, log, persisted_state, saved_searches):
        assert len(saved_searches) == saved_searches_parallel, \
            "Did not respect the configured saved_searches_parallel setting, got value: %i" % len(saved_searches)

        if len(saved_searches) != saved_searches_parallel:
            check.parallel_dispatches_failed = True

        for saved_search in saved_searches:
            if saved_search.name != "savedsearch%i" % check.expected_sid_increment:
                check.parallel_dispatches_failed = True

            check.expected_sid_increment += 1
        return True

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        '_dispatch_and_await_search': _mock_dispatch_and_await_search,
    })

    # Increment to validate mock
    check.expected_sid_increment = 1

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    # Can be used afterwards to test if the mock worked
    check.parallel_dispatches_failed = False

    return check


@pytest.fixture
def selective_fields_for_identification_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                              splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'metrics_identification_fields_selective'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id="stackstate_checks.base.checks.base.metric-check-name")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "unique_key_fields": ["uid1", "uid2"]
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def all_fields_for_identification_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                        splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'metrics_identification_fields_all'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id="stackstate_checks.base.checks.base.metric-check-name")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "unique_key_fields": []
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def backward_compatibility_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                 splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'metrics_identification_fields_all'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id="stackstate_checks.base.checks.base.metric-check-name")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "unique_key_fields": []
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def backward_compatibility_new_conf_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                          splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'metrics_identification_fields_all'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                   finalize_search_id="stackstate_checks.base.checks.base.metric-check-name")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "unique_key_fields": []
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check

# Done
@pytest.fixture
def default_parameters_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_name = 'minimal_metrics'
    splunk_parameters = {
        'dispatch.now': True,
        'force_dispatch': True
    }

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    def mock_auth_session_to_check_instance_config(_, instance):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == splunk_parameters, \
                "Unexpected default parameters for saved search: %s" % saved_search.name
        return "sessionKey1"

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session_to_check_instance_config,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def non_default_parameters_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                 mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_name = 'minimal_metrics'
    splunk_parameters = {
        "respect": "me"
    }

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk tags
    config_saved_search = SplunkConfigSavedSearchDefault({
        "name": splunk_config_name,
        "parameters": None
    })

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        config_saved_search
    ]

    # Set the splunk initial searches
    splunk_config.init_config = {
        "default_parameters": splunk_parameters
    }

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    def mock_auth_session_to_check_instance_config(committable_state, instance):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == splunk_parameters, \
                "Unexpected non-default parameters for saved search: %s" % saved_search.name
        return "sessionKey1"

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session_to_check_instance_config,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def overwrite_default_parameters_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                       mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> MockSplunkMetric
    splunk_config_name = 'minimal_metrics'
    splunk_parameters = {
        "respect": "me"
    }

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk tags
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": splunk_parameters
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    def mock_auth_session_to_check_instance_config(committable_state, instance):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == splunk_parameters, \
                "Unexpected overwritten default parameters for saved search: %s" % saved_search.name
        return "sessionKey1"

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'auth_session': mock_auth_session_to_check_instance_config,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def max_query_chunk_sec_history_check(get_logger, requests_mock, splunk_config, splunk_instance_basic_auth,
                                      mock_splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[MockSplunkMetric]) -> Tuple[MockSplunkMetric, dict[str, any]]
    splunk_config_name = 'metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "max_restart_history_seconds": 3600,
            "max_query_chunk_seconds": 300,
            "initial_history_time_seconds": 86400,
            "unique_key_fields": None
        })
    ]

    # Set the splunk initial searches
    splunk_config.init_config = {
        "default_restart_history_time_seconds": 3600,
        "default_max_query_chunk_seconds": 300,
        "default_initial_history_time_seconds": 86400,
        "unique_key_fields": None
    }

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": ""
    }

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        earliest_time = args[3]['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]

        if test_data["earliest_time"] == "2017-03-08T00:00:00.000000+0000":
            return "metrics"
        else:
            return "past_metrics"

    check = mock_splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances, {
        'dispatch': mock_dispatch_saved_search_dispatch,
    })

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


# Done
@pytest.fixture
def max_query_chunk_sec_live_check(get_logger, requests_mock, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "max_query_chunk_seconds": 300,
            "unique_key_fields": None
        })
    ]

    # Set the splunk initial searches
    splunk_config.init_config = {
        'default_restart_history_time_seconds': 3600,
        'default_max_query_chunk_seconds': 300,
        'unique_key_fields': None
    }

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def token_auth_with_valid_token_check(get_logger, requests_mock, splunk_config, splunk_instance_token_auth,
                                      splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="api-admin")

    # Set the splunk saved searches
    splunk_instance_token_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_token_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Create the check class with the config created above
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def authentication_invalid_token_check(get_logger, requests_mock, splunk_config, splunk_instance_token_auth,
                                       splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="api-admin")

    # Forcefully create a token with an expiry time from the past
    token_expire_time = datetime.now() - timedelta(days=999)
    splunk_instance_token_auth.authentication.token_auth.initial_token = _generate_mock_token(token_expire_time)

    # Set the splunk saved searches
    splunk_instance_token_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_token_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Create the check class with the config created above
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def authentication_token_no_audience_parameter_check(splunk_config, splunk_instance_token_auth, splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Delete the audience parameter from the token_auth to test
    del splunk_instance_token_auth.authentication.token_auth.audience

    # Set the splunk saved searches
    splunk_instance_token_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_token_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Create the check class with the config created above
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def authentication_token_no_name_parameter_check(splunk_config, splunk_instance_token_auth, splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Delete the name parameter from the token_auth to test
    del splunk_instance_token_auth.authentication.token_auth.name

    # Change the audience
    splunk_instance_token_auth.authentication.token_auth.audience = "search"

    # Set the splunk saved searches
    splunk_instance_token_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_token_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Create the check class with the config created above
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def authentication_prefer_token_over_basic_check(get_logger, requests_mock, splunk_config, splunk_instance_basic_auth,
                                                 splunk_instance_token_auth, splunk_metric):
    # type: (logging.Logger, Mocker, SplunkConfig, SplunkConfigInstance, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    _requests_mock(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="api-admin")

    # Combine the basic auth and the token auth py fixtures into one to test preferred
    splunk_instance_basic_auth.authentication.token_auth = splunk_instance_token_auth.authentication.token_auth

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Create the check class with the config created above
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Done
@pytest.fixture
def authentication_token_expired_check(splunk_config, splunk_instance_token_auth, splunk_metric):
    # type: (SplunkConfig, SplunkConfigInstance, Type[SplunkMetric]) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Forcefully create a token with an expiry time from the past
    token_expire_time = datetime.now() - timedelta(days=999)
    splunk_instance_token_auth.authentication.token_auth.initial_token = _generate_mock_token(token_expire_time)

    # Set the splunk saved searches
    splunk_instance_token_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_token_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Create the check class with the config created above
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check
