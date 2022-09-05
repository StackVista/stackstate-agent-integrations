# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
import logging
import inspect

from stackstate_checks.splunk.config import AuthType
from requests_mock import Mocker
from datetime import timedelta, datetime
from stackstate_checks.errors import CheckException
from typing import Type, Tuple

from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.saved_search_helper import SavedSearchesTelemetry
from stackstate_checks.splunk_metric import SplunkMetric
from .common import HOST, PORT, USER, PASSWORD
from .mock import mock_finalize_sid_exception, mock_polling_search, generate_mock_token, apply_request_mock_routes
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigInstance, SplunkConfig, \
    SplunkConfigSavedSearchDefault

# Type safety mappings
SplunkMetricDataTuple = Tuple[SplunkMetric, dict[str, any]]
SplunkMetricType = Type[SplunkMetric]
Instance = SplunkConfigInstance
Config = SplunkConfig
Logger = logging.Logger
RequestMocker = Mocker


@pytest.fixture
def get_logger():  # type: () -> Logger
    return logging.getLogger('{}.{}'.format(__name__, SplunkMetric.CHECK_NAME))


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
                'initial_token': generate_mock_token(token_expire_time),
                'audience': "admin",
                'renewal_days': 10
            }
        },
        'tags': []
    })
    splunk_config.validate(partial=True)
    return splunk_config


@pytest.fixture
def splunk_metric(telemetry, aggregator, topology, transaction, state):
    # type: (any, any, any, any, any) -> SplunkMetricType

    # Bring back the splunk mock metrics
    yield SplunkMetric

    # Clean the singleton states that could have been used
    telemetry.reset()
    aggregator.reset()
    topology.reset()
    transaction.reset()
    state.reset()


@pytest.fixture
def error_response_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, MockSplunkMetricType) -> MockSplunkMetric
    splunk_config_name = 'error'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk tags
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

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


# Not a pyfixture, Require multiple runs
def metric_check(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric,
                 patch_finalize_sid=False, force_finalize_sid_exception=False):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType, bool, bool) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name)

    # Splunk Config Tags
    splunk_instance_basic_auth.tags = ['mytag', 'mytag2']

    # Set the splunk tags
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

    if force_finalize_sid_exception:
        # Monkey Patches for Mock Functions
        monkeypatch.setattr(SplunkClient, "finalize_sid", mock_finalize_sid_exception)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def empty_metrics(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'empty'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Splunk Config Tags
    splunk_instance_basic_auth.tags = []

    # Set the splunk tags
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

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def minimal_metrics(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Splunk Config Tags
    splunk_instance_basic_auth.tags = []

    # Set the splunk tags
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

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def partially_incomplete_metrics(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'partially_incomplete_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Splunk Config Tags
    splunk_instance_basic_auth.tags = []

    # Set the splunk tags
    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
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
def full_metrics(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'full_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Splunk Config Tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk tags
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

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def alternative_fields_metrics(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'alternative_fields_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "metric_name_field": "mymetric",
            "metric_value_field": "myvalue",
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
def fixed_metric_name(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'alternative_fields_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

    # Set the splunk tags
    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "metric_name": "custommetric",
            "metric_value_field": "myvalue",
            "parameters": {}
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
def warning_on_missing_fields(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = "incomplete_metrics"

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name)

    # Set the splunk tags
    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": "incomplete_metrics",
            "parameters": {}
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
def same_data_metrics(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = "duplicate_metrics"

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name)

    # Set the splunk tags
    splunk_instance_basic_auth.saved_searches = [  # Splunk Saved Searches
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {}
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


def earliest_time_and_duplicates(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                 splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetricDataTuple
    splunk_config_name = "poll"

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name, ignore_search=True)
    apply_request_mock_routes(requests_mock, request_id="poll1", logger=get_logger, audience="admin",
                              finalize_search_id="poll1", ignore_search=True)

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk tags
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "batch_size": 2
        })
    ]

    # Add the splunk instance into the config instances
    splunk_config.instances.append(splunk_instance_basic_auth)

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Used to validate which searches have been executed
    test_data = {
        "expected_searches": ["poll"],
        "sid": "",
        "earliest_time": "",
        "throw": False
    }

    def mock_dispatch_saved_search_dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        print("Running Mock: mock_dispatch_saved_search_dispatch")

        if test_data["throw"]:
            raise CheckException("Is broke it")

        earliest_time = parameters['dispatch.earliest_time']

        # make sure the ignore search flag is always false
        assert ignore_saved_search_errors is False

        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]

        return test_data["sid"]

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)
    monkeypatch.setattr(SplunkClient, "saved_search_results", mock_polling_search)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


@pytest.fixture
def delayed_start(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, MockSplunkMetricType) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
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

    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


def continue_after_restart(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                           splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetricDataTuple
    splunk_config_name = 'empty'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id="empty")

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

    def dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        earliest_time = parameters['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]

        # make sure the ignore search flag is always false
        if test_data["latest_time"] is None:
            dispatch_latest_time = 'dispatch.latest_time' in parameters
            assert dispatch_latest_time is False
        elif test_data["latest_time"] != "":
            assert parameters['dispatch.latest_time'] == test_data["latest_time"]

        return "empty"

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", dispatch)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


@pytest.fixture
def query_initial_history(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                          splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetricDataTuple
    splunk_config_name = 'empty'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id="minimal_metrics", logger=get_logger, audience="admin",
                              finalize_search_id="minimal_metrics")

    # Set the splunk tags
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    # Set the splunk saved searches
    splunk_instance_basic_auth.saved_searches = [
        SplunkConfigSavedSearchDefault({
            "name": splunk_config_name,
            "parameters": {},
            "max_initial_history_seconds": 86400,
            "max_query_chunk_seconds": 3600,
            "initial_history_time_seconds": 86400  # Override the Schematic default
        })
    ]

    # Set the splunk initial searches
    splunk_config.init_config = {
        'default_initial_history_time_seconds': 86400,
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

    def mock_dispatch_saved_search_dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        earliest_time = parameters['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]
        # make sure the ignore search flag is always false
        if test_data["latest_time"] is None:
            dispatch_latest_time = 'dispatch.latest_time' in parameters
            assert dispatch_latest_time is False
        elif test_data["latest_time"] != "":
            assert parameters['dispatch.latest_time'] == test_data["latest_time"]

        return "minimal_metrics"

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


def max_restart_time(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                     splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetricDataTuple
    splunk_config_name = 'empty'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
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

    def mock_dispatch_saved_search_dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        earliest_time = parameters['dispatch.earliest_time']

        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]
        return splunk_config_name

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


@pytest.fixture
def keep_time_on_failure(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                         splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetricDataTuple

    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
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

    def mock_dispatch_saved_search_dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        earliest_time = parameters['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]

        return splunk_config_name

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


@pytest.fixture
def advance_time_on_success(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                            splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetricDataTuple

    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
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

    def mock_dispatch_saved_search_dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        earliest_time = parameters['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]
        return splunk_config_name

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


@pytest.fixture
def wildcard_searches(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                      splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetricDataTuple
    splunk_config_name = 'minimal_metrics'
    splunk_config_match = 'minimal_*'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

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

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", mocked_saved_searches)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, data


@pytest.fixture
def saved_searches_error(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                         splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric

    splunk_config_name = 'full_metrics'
    splunk_config_match = '.*metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

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

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", mocked_saved_searches)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def saved_searches_ignore_error(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric

    splunk_config_name = 'full_metrics'
    splunk_config_match = '.*metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

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

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", mocked_saved_searches)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def individual_dispatch_failures(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                 splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_match = '.*metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id="minimal_metrics", logger=get_logger, audience="admin",
                              finalize_search_id="minimal_metrics")
    apply_request_mock_routes(requests_mock, request_id="full_metrics", logger=get_logger, audience="admin",
                              force_dispatch_search_failure=True,
                              finalize_search_id="full_metrics")

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
        'saved_searches': ["minimal_metrics", "full_metrics"]
    }

    def _mocked_saved_searches(*args, **kwargs):
        return data['saved_searches']

    def _mocked_failing_search(*args, **kwargs):
        sid = args[3].name
        if sid == "full_metrics":
            raise Exception("BOOM")
        else:
            return sid

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", _mocked_saved_searches)
    monkeypatch.setattr(SavedSearchesTelemetry, "_dispatch_saved_search", _mocked_failing_search)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def individual_search_failures(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                               splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_match = '.*metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id="minimal_metrics", logger=get_logger, audience="admin")
    apply_request_mock_routes(requests_mock, request_id="full_metrics", logger=get_logger, audience="admin",
                              force_search_failure=True)

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

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", _mocked_saved_searches)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def search_full_failure(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                        splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'full_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

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

    data = {
        'saved_searches': ["full_metrics"]
    }

    def mocked_saved_searches(*args, **kwargs):
        return data['saved_searches']

    def mock_dispatch_saved_search(*args, **kwargs):
        raise Exception("BOOM")

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", mocked_saved_searches)
    monkeypatch.setattr(SavedSearchesTelemetry, "_dispatch_saved_search", mock_dispatch_saved_search)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def respect_parallel_dispatches(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_names = ['savedsearch1', 'savedsearch2', 'savedsearch3', 'savedsearch4']

    saved_searches_parallel = 2

    # Mock the HTTP Requests
    for request_id in splunk_config_names:
        apply_request_mock_routes(requests_mock, request_id=request_id, logger=get_logger, audience="admin",
                                  ignore_search=True)

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

    def _mock_dispatch_and_await_search(self, process_data, service_check, log, persisted_state, saved_searches):
        assert len(saved_searches) == saved_searches_parallel, \
            "Did not respect the configured saved_searches_parallel setting, got value: %i" % len(saved_searches)

        if len(saved_searches) != saved_searches_parallel:
            check.parallel_dispatches_failed = True

        for saved_search in saved_searches:
            if saved_search.name != "savedsearch%i" % check.expected_sid_increment:
                check.parallel_dispatches_failed = True

            check.expected_sid_increment += 1
        return True

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SavedSearchesTelemetry, "_dispatch_and_await_search", _mock_dispatch_and_await_search)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

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
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'metrics_identification_fields_selective'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name)

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
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'metrics_identification_fields_all'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name)

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


@pytest.fixture
def backward_compatibility_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                 splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'metrics_identification_fields_all'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name)

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


@pytest.fixture
def backward_compatibility_new_conf_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                          splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric

    splunk_config_name = 'metrics_identification_fields_all'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name)

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

@pytest.fixture
def default_parameters_check(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                             splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric

    splunk_config_name = 'minimal_metrics'
    splunk_parameters = {
        'dispatch.now': True,
        'force_dispatch': True
    }

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

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

    def mock_auth_session_to_check_instance_config(self, committable_state, instance=None):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == splunk_parameters, \
                "Unexpected default parameters for saved search: %s" % saved_search.name

        if self.instance_config.auth_type == AuthType.BasicAuth:
            self.log.debug("Using user/password based authentication mechanism")
            self._basic_auth()
        elif self.instance_config.auth_type == AuthType.TokenAuth:
            self.log.debug("Using token based authentication mechanism")
            self._token_auth_session(committable_state)

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "auth_session", mock_auth_session_to_check_instance_config)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def non_default_parameters_check(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                 splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'
    splunk_parameters = {
        "respect": "me"
    }

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

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

    def mock_auth_session_to_check_instance_config(self, committable_state, instance):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == splunk_parameters, \
                "Unexpected non-default parameters for saved search: %s" % saved_search.name

        if self.instance_config.auth_type == AuthType.BasicAuth:
            self.log.debug("Using user/password based authentication mechanism")
            self._basic_auth()
        elif self.instance_config.auth_type == AuthType.TokenAuth:
            self.log.debug("Using token based authentication mechanism")
            self._token_auth_session(committable_state)

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "auth_session", mock_auth_session_to_check_instance_config)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def overwrite_default_parameters_check(monkeypatch, requests_mock, get_logger, splunk_config,
                                       splunk_instance_basic_auth, splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric

    splunk_config_name = 'minimal_metrics'
    splunk_parameters = {
        "respect": "me"
    }

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin")

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

    def mock_auth_session_to_check_instance_config(self, committable_state, instance):
        for saved_search in instance.saved_searches.searches:
            assert saved_search.parameters == splunk_parameters, \
                "Unexpected overwritten default parameters for saved search: %s" % saved_search.name

        if self.instance_config.auth_type == AuthType.BasicAuth:
            self.log.debug("Using user/password based authentication mechanism")
            self._basic_auth()
        elif self.instance_config.auth_type == AuthType.TokenAuth:
            self.log.debug("Using token based authentication mechanism")
            self._token_auth_session(committable_state)

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "auth_session", mock_auth_session_to_check_instance_config)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


def max_query_chunk_sec_history_check(monkeypatch, get_logger, requests_mock, splunk_config, splunk_instance_basic_auth,
                                      splunk_metric):
    # type: (any, Logger, RequestMocker, Config, Instance, SplunkMetricType) -> SplunkMetricDataTuple

    splunk_config_name = 'metrics'
    splunk_config_name_alt = 'past_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name)
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name_alt, logger=get_logger, audience="admin",
                              finalize_search_id=splunk_config_name_alt)

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
        if test_data["earliest_time"] == "2017-03-08T00:00:00.000000+0000":
            return splunk_config_name
        else:
            return splunk_config_name_alt

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check, test_data


@pytest.fixture
def max_query_chunk_sec_live_check(monkeypatch, requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                   splunk_metric):
    # type: (any, RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id="minimal_metrics", logger=get_logger, audience="admin")

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

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        return "minimal_metrics"

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def token_auth_with_valid_token_check(get_logger, requests_mock, splunk_config, splunk_instance_token_auth,
                                      splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="api-admin")

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


@pytest.fixture
def authentication_invalid_token_check(get_logger, requests_mock, splunk_config, splunk_instance_token_auth,
                                       splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="api-admin")

    # Forcefully create a token with an expiry time from the past
    token_expire_time = datetime.now() - timedelta(days=999)
    splunk_instance_token_auth.authentication.token_auth.initial_token = generate_mock_token(token_expire_time)

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


@pytest.fixture
def authentication_token_no_audience_parameter_check(splunk_config, splunk_instance_token_auth, splunk_metric):
    # type: (Config, Instance, SplunkMetricType) -> SplunkMetric
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


@pytest.fixture
def authentication_token_no_name_parameter_check(splunk_config, splunk_instance_token_auth, splunk_metric):
    # type: (Config, Instance, SplunkMetricType) -> SplunkMetric
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


@pytest.fixture
def authentication_prefer_token_over_basic_check(requests_mock, get_logger, splunk_config, splunk_instance_basic_auth,
                                                 splunk_instance_token_auth, splunk_metric):
    # type: (RequestMocker, Logger, Config, Instance, SplunkConfigInstance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock, request_id=splunk_config_name, logger=get_logger, audience="api-admin")

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


@pytest.fixture
def authentication_token_expired_check(splunk_config, splunk_instance_token_auth, splunk_metric):
    # type: (Config, Instance, SplunkMetricType) -> SplunkMetric
    splunk_config_name = 'minimal_metrics'

    # Forcefully create a token with an expiry time from the past
    token_expire_time = datetime.now() - timedelta(days=999)
    splunk_instance_token_auth.authentication.token_auth.initial_token = generate_mock_token(token_expire_time)

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
