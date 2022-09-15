# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

import pytest
import logging
import inspect

import requests

from stackstate_checks.base.stubs.aggregator import AggregatorStub
from stackstate_checks.base.stubs.state import StateStub
from stackstate_checks.base.stubs.telemetry import TelemetryStub
from stackstate_checks.base.stubs.topology import TopologyStub
from stackstate_checks.base.stubs.transaction import TransactionStub
from stackstate_checks.dev import docker_run, WaitFor
from stackstate_checks.splunk.config import AuthType, SplunkInstanceConfig
from requests_mock import Mocker
from datetime import timedelta, datetime
from stackstate_checks.errors import CheckException
from typing import Type, Tuple, Dict, Generator
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.saved_search_helper import SavedSearchesTelemetry
from stackstate_checks.splunk_metric import SplunkMetric, DEFAULT_SETTINGS
from .common import HOST, PORT, USER, PASSWORD
from .mock import mock_finalize_sid_exception, mock_polling_search, generate_mock_token, apply_request_mock_routes
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigInstance, SplunkConfig, \
    SplunkConfigSavedSearchDefault


@pytest.fixture
def get_logger():  # type: () -> logging.Logger
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
def splunk_metric(telemetry,  # type: TelemetryStub
                  aggregator,  # type: AggregatorStub
                  topology,  # type: TopologyStub
                  transaction,  # type: TransactionStub
                  state  # type: StateStub
                  ):  # type: (...) -> Type[SplunkMetric]

    # Bring back the splunk mock metrics
    yield SplunkMetric

    # Clean the singleton states that could have been used
    telemetry.reset()
    aggregator.reset()
    topology.reset()
    transaction.reset()
    state.reset()


def merge_two_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z


@pytest.fixture
def config():  # type: () -> Dict
    return {}


@pytest.fixture
def init_config():  # type: () -> Dict
    return {}


@pytest.fixture
def saved_search_config():  # type: () -> Dict
    return {}


@pytest.fixture
def set_authentication_mode_to_token(authentication_mode,  # type: Dict
                                     splunk_instance_token_auth  # type: SplunkConfigInstance
                                     ):  # type: (...) -> None
    authentication_mode["mode"] = splunk_instance_token_auth


@pytest.fixture
def authentication_mode(splunk_instance_basic_auth,  # type: SplunkConfigInstance
                        ):  # type: (...) -> Dict
    return {
        "mode": splunk_instance_basic_auth
    }


# Base Structure For The Checks
@pytest.fixture
def check(requests_mock,  # type: Mocker
          get_logger,  # type: logging.Logger
          splunk_config,  # type: SplunkConfig
          authentication_mode,  # type: Dict
          splunk_metric,  # type: Type[SplunkMetric]
          config,  # type: Dict
          init_config,  # type: Dict
          saved_search_config  # type: Dict
          ):  # type: (...) -> SplunkMetric

    # Mock the HTTP Requests
    apply_request_mock_routes(requests_mock,
                              logger=get_logger,
                              request_id=config.get("request_id"),
                              audience=config.get("audience", "admin"),
                              finalize_search_id=config.get("finalize_search_id", None),
                              ignore_search=config.get("ignore_search", False),
                              force_search_failure=config.get("force_search_failure", False),
                              force_dispatch_search_failure=config.get("force_dispatch_search_failure", False)
                              )

    alternative_routes = config.get("mock_alternative_routes")
    if alternative_routes is not None:
        for route in alternative_routes:
            # Mock alternative HTTP Requests
            apply_request_mock_routes(requests_mock,
                                      logger=get_logger,
                                      request_id=route.get("request_id"),
                                      audience=route.get("audience", "admin"),
                                      finalize_search_id=route.get("finalize_search_id", None),
                                      ignore_search=route.get("ignore_search", False),
                                      force_search_failure=route.get("force_search_failure", False),
                                      force_dispatch_search_failure=route.get("force_dispatch_search_failure", False)
                                      )

    parameters = merge_two_dicts({
        "name": config.get("override_config_name", config["request_id"]),
        "parameters": config.get("parameters", {}),
    }, saved_search_config)

    # Set the splunk tags
    authentication_mode["mode"].saved_searches = [
        SplunkConfigSavedSearchDefault(parameters)
    ]

    for saved_search in config.get("merge_saved_search", []):
        authentication_mode["mode"].saved_searches.append(saved_search)

    splunk_config.init_config = init_config

    # Add the splunk instance into the config instances
    splunk_config.instances.append(authentication_mode["mode"])

    # Validate the config, authentication and saved_search data we are sending
    splunk_config.validate()

    # Check
    check = splunk_metric(SplunkMetric.CHECK_NAME, splunk_config.init_config, {}, splunk_config.instances)

    # We set the check id to the current function name to prevent a blank check id
    check.check_id = inspect.stack()[0][3]

    return check


@pytest.fixture
def config_minimal_metrics(config,  # type: any
                           splunk_instance_basic_auth  # type: SplunkConfigInstance
                           ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"


@pytest.fixture
def config_error(config,  # type: any
                 splunk_instance_basic_auth  # type: SplunkConfigInstance
                 ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "error"
    config["audience"] = "admin"
    config["force_search_failure"] = True


@pytest.fixture
def config_empty(config,  # type: any
                 splunk_instance_basic_auth  # type: SplunkConfigInstance
                 ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "empty"
    config["audience"] = "admin"


@pytest.fixture
def config_partially_incomplete_metrics(config,  # type: any
                                        splunk_instance_basic_auth  # type: SplunkConfigInstance
                                        ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "partially_incomplete_metrics"
    config["audience"] = "admin"


@pytest.fixture
def config_full_metrics(config,  # type: any
                        splunk_instance_basic_auth  # type: SplunkConfigInstance
                        ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    config["request_id"] = "full_metrics"
    config["audience"] = "admin"


@pytest.fixture
def config_alternative_fields_metrics(config,  # type: any
                                      saved_search_config,  # type: any
                                      splunk_instance_basic_auth  # type: SplunkConfigInstance
                                      ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []

    config["request_id"] = "alternative_fields_metrics"
    config["audience"] = "admin"

    saved_search_config["metric_name_field"] = "mymetric"
    saved_search_config["metric_value_field"] = "myvalue"


@pytest.fixture
def config_fixed_metric_name(config,  # type: any
                             saved_search_config,  # type: any
                             splunk_instance_basic_auth  # type: SplunkConfigInstance
                             ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []

    config["request_id"] = "alternative_fields_metrics"
    config["audience"] = "admin"

    saved_search_config["metric_name"] = "custommetric"
    saved_search_config["metric_value_field"] = "myvalue"


@pytest.fixture
def config_warning_on_missing_fields(config,  # type: any
                                     splunk_instance_basic_auth  # type: SplunkConfigInstance
                                     ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "incomplete_metrics"
    config["audience"] = "admin"
    config["finalize_search_id"] = "incomplete_metrics"


@pytest.fixture
def config_same_data_metrics(config,  # type: any
                             splunk_instance_basic_auth  # type: SplunkConfigInstance
                             ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "duplicate_metrics"
    config["audience"] = "admin"
    config["finalize_search_id"] = "duplicate_metrics"


@pytest.fixture
def config_delayed_start(config,  # type: any
                         init_config,  # type: any
                         splunk_instance_basic_auth  # type: SplunkConfigInstance
                         ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"
    config["finalize_search_id"] = "minimal_metrics"
    init_config["default_initial_delay_seconds"] = 60


@pytest.fixture
def config_max_restart_time(config,  # type: any
                            init_config,  # type: any
                            saved_search_config,  # type: any
                            splunk_instance_basic_auth  # type: SplunkConfigInstance
                            ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    config["request_id"] = "empty"
    config["finalize_search_id"] = "empty"
    config["audience"] = "admin"
    init_config["max_restart_history_seconds"] = 3600
    init_config["max_query_chunk_seconds"] = 3600
    saved_search_config["max_restart_history_seconds"] = 3600
    saved_search_config["max_query_chunk_seconds"] = 3600


@pytest.fixture
def patch_max_restart_time(monkeypatch):  # type: (...) -> Dict[str, any]
    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": ""
    }

    def mock_dispatch_saved_search_dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        earliest_time = parameters['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]
        return "empty"

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    return test_data


@pytest.fixture
def config_metric_check(config,  # type: any
                        init_config,  # type: any
                        saved_search_config,  # type: any
                        splunk_instance_basic_auth  # type: SplunkConfigInstance
                        ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ['mytag', 'mytag2']
    config["request_id"] = "minimal_metrics"
    config["finalize_search_id"] = "minimal_metrics"
    config["audience"] = "admin"


def patch_metric_check(monkeypatch,  # type: any
                       force_finalize_sid_exception=False  # type: bool
                       ):  # type: (...) -> None

    if force_finalize_sid_exception:
        # Monkey Patches for Mock Functions
        monkeypatch.setattr(SplunkClient, "finalize_sid", mock_finalize_sid_exception)


@pytest.fixture
def config_test_default_parameters(config,  # type: any
                                   init_config,  # type: any
                                   saved_search_config,  # type: any
                                   splunk_instance_basic_auth  # type: SplunkConfigInstance
                                   ):  # type: (...) -> None
    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"
    config["parameters"] = None


@pytest.fixture
def patch_default_parameters_check(monkeypatch,  # type: any
                                   check,  # type: SplunkMetric
                                   ):  # type: (...) -> None

    splunk_parameters = {
        'dispatch.now': True,
        'force_dispatch': True
    }

    def mock_auth_session_to_check_instance_config(self, committable_state):
        for saved_search in check.splunk_telemetry_instance.saved_searches.searches:
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


@pytest.fixture
def config_earliest_time_and_duplicates(config,  # type: any
                                        init_config,  # type: any
                                        saved_search_config,  # type: any
                                        splunk_instance_basic_auth  # type: SplunkConfigInstance
                                        ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    config["request_id"] = "poll"
    config["finalize_search_id"] = "poll"
    config["audience"] = "admin"
    config["ignore_search"] = True

    config["mock_alternative_routes"] = [
        {
            "request_id": "poll1",
            "finalize_search_id": "poll1",
            "audience": config["audience"],
            "ignore_search": config["ignore_search"]
        }
    ]

    saved_search_config["batch_size"] = 2


@pytest.fixture
def patch_earliest_time_and_duplicates(monkeypatch,  # type: any
                                       ):  # type: (...) -> Dict[str, any]
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

    return test_data


@pytest.fixture
def config_continue_after_restart(config,  # type: any
                                  init_config,  # type: any
                                  saved_search_config,  # type: any
                                  splunk_instance_basic_auth  # type: SplunkConfigInstance
                                  ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]

    config["request_id"] = "empty"
    config["finalize_search_id"] = "empty"
    config["audience"] = "admin"

    saved_search_config["max_restart_history_seconds"] = 86400
    saved_search_config["max_query_time_range"] = 3600

    init_config["default_max_restart_history_seconds"] = 86400
    init_config["default_max_query_time_range"] = 3600


@pytest.fixture
def patch_continue_after_restart(monkeypatch,  # type: any
                                 ):  # type: (...) -> Dict[str, any]
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

    return test_data


@pytest.fixture
def config_selective_fields_for_identification_check(config,  # type: any
                                                     init_config,  # type: any
                                                     saved_search_config,  # type: any
                                                     splunk_instance_basic_auth  # type: SplunkConfigInstance
                                                     ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "metrics_identification_fields_selective"
    config["finalize_search_id"] = "metrics_identification_fields_selective"
    config["audience"] = "admin"
    saved_search_config["unique_key_fields"] = ["uid1", "uid2"]


@pytest.fixture
def config_all_fields_for_identification_check(config,  # type: any
                                               init_config,  # type: any
                                               saved_search_config,  # type: any
                                               splunk_instance_basic_auth  # type: SplunkConfigInstance
                                               ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "metrics_identification_fields_all"
    config["finalize_search_id"] = "metrics_identification_fields_all"
    config["audience"] = "admin"
    saved_search_config["unique_key_fields"] = []


@pytest.fixture
def config_backward_compatibility_check(config,  # type: any
                                        init_config,  # type: any
                                        saved_search_config,  # type: any
                                        splunk_instance_basic_auth  # type: SplunkConfigInstance
                                        ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "metrics_identification_fields_all"
    config["finalize_search_id"] = "metrics_identification_fields_all"
    config["audience"] = "admin"
    saved_search_config["unique_key_fields"] = []


@pytest.fixture
def config_backward_compatibility_new_conf_check(config,  # type: any
                                                 init_config,  # type: any
                                                 saved_search_config,  # type: any
                                                 splunk_instance_basic_auth  # type: SplunkConfigInstance
                                                 ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []
    config["request_id"] = "metrics_identification_fields_all"
    config["finalize_search_id"] = "metrics_identification_fields_all"
    config["audience"] = "admin"
    saved_search_config["unique_key_fields"] = []


@pytest.fixture
def config_query_initial_history(config,  # type: any
                                 init_config,  # type: any
                                 saved_search_config,  # type: any
                                 splunk_instance_basic_auth  # type: SplunkConfigInstance
                                 ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    config["override_config_name"] = "empty"
    config["request_id"] = "minimal_metrics"
    config["finalize_search_id"] = "minimal_metrics"
    config["audience"] = "admin"

    saved_search_config["max_initial_history_seconds"] = 86400
    saved_search_config["initial_history_time_seconds"] = 86400
    saved_search_config["max_query_chunk_seconds"] = 3600

    init_config["default_initial_history_time_seconds"] = 86400
    init_config["default_max_query_chunk_seconds"] = 3600


@pytest.fixture
def patch_query_initial_history(monkeypatch,  # type: any
                                ):  # type: (...) -> Dict[str, any]
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

    return test_data


@pytest.fixture
def config_keep_time_on_failure(config,  # type: any
                                init_config,  # type: any
                                saved_search_config,  # type: any
                                splunk_instance_basic_auth  # type: SplunkConfigInstance
                                ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    config["request_id"] = "minimal_metrics"
    config["finalize_search_id"] = "minimal_metrics"
    config["audience"] = "admin"


@pytest.fixture
def patch_keep_time_on_failure(monkeypatch,  # type: any
                               ):  # type: (...) -> Dict[str, any]
    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": ""
    }

    def mock_dispatch_saved_search_dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        earliest_time = parameters['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]

        return "minimal_metrics"

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    return test_data


@pytest.fixture
def config_advance_time_on_success(config,  # type: any
                                   init_config,  # type: any
                                   saved_search_config,  # type: any
                                   splunk_instance_basic_auth  # type: SplunkConfigInstance
                                   ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    config["request_id"] = "minimal_metrics"
    config["finalize_search_id"] = "minimal_metrics"
    config["audience"] = "admin"


@pytest.fixture
def patch_advance_time_on_success(monkeypatch,  # type: any
                                  ):  # type: (...) -> Dict[str, any]
    # Used to validate which searches have been executed
    test_data = {
        "earliest_time": ""
    }

    def mock_dispatch_saved_search_dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        earliest_time = parameters['dispatch.earliest_time']
        if test_data["earliest_time"] != "":
            assert earliest_time == test_data["earliest_time"]
        return "minimal_metrics"

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)

    return test_data


@pytest.fixture
def config_wildcard_searches(config,  # type: any
                             init_config,  # type: any
                             saved_search_config,  # type: any
                             splunk_instance_basic_auth  # type: SplunkConfigInstance
                             ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"
    config["override_config_name"] = None

    saved_search_config["match"] = "minimal_*"


@pytest.fixture
def patch_wildcard_searches(monkeypatch,  # type: any
                            ):  # type: (...) -> Dict[str, any]

    data = {
        'saved_searches': []
    }

    def mocked_saved_searches(*args, **kwargs):
        return data['saved_searches']

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", mocked_saved_searches)

    return data


@pytest.fixture
def config_saved_searches_error(config,  # type: any
                                init_config,  # type: any
                                saved_search_config,  # type: any
                                splunk_instance_basic_auth  # type: SplunkConfigInstance
                                ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    config["request_id"] = "full_metrics"
    config["audience"] = "admin"
    config["override_config_name"] = None
    saved_search_config["match"] = ".*metrics"


@pytest.fixture
def patch_saved_searches_error(monkeypatch,  # type: any
                               ):  # type: (...) -> None
    def mocked_saved_searches(*args, **kwargs):
        raise Exception("Boom")

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", mocked_saved_searches)


@pytest.fixture
def config_saved_searches_ignore_error(config,  # type: any
                                       init_config,  # type: any
                                       saved_search_config,  # type: any
                                       splunk_instance_basic_auth  # type: SplunkConfigInstance
                                       ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    splunk_instance_basic_auth.ignore_saved_search_errors = True

    config["request_id"] = "full_metrics"
    config["audience"] = "admin"
    config["override_config_name"] = None
    saved_search_config["match"] = ".*metrics"


@pytest.fixture
def patch_saved_searches_ignore_error(monkeypatch,  # type: any
                                      ):  # type: (...) -> None
    def mocked_saved_searches(*args, **kwargs):
        raise Exception("Boom")

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", mocked_saved_searches)


@pytest.fixture
def config_individual_dispatch_failures(config,  # type: any
                                        init_config,  # type: any
                                        saved_search_config,  # type: any
                                        splunk_instance_basic_auth  # type: SplunkConfigInstance
                                        ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    splunk_instance_basic_auth.ignore_saved_search_errors = True

    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"
    config["override_config_name"] = None
    config["mock_alternative_routes"] = [
        {
            "request_id": "full_metrics",
            "finalize_search_id": "full_metrics",
            "force_dispatch_search_failure": True,
            "audience": config["audience"]
        }
    ]

    saved_search_config["match"] = ".*metrics"


@pytest.fixture
def patch_individual_dispatch_failures(monkeypatch,  # type: any
                                       ):  # type: (...) -> None
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


@pytest.fixture
def config_individual_search_failures(config,  # type: any
                                      init_config,  # type: any
                                      saved_search_config,  # type: any
                                      splunk_instance_basic_auth  # type: SplunkConfigInstance
                                      ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    splunk_instance_basic_auth.ignore_saved_search_errors = True

    saved_search_config["match"] = ".*metrics"

    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"
    config["override_config_name"] = None

    config["mock_alternative_routes"] = [
        {
            "request_id": "full_metrics",
            "force_search_failure": True,
            "audience": config["audience"]
        }
    ]


@pytest.fixture
def patch_individual_search_failures(monkeypatch,  # type: any
                                     ):  # type: (...) -> None
    data = {
        'saved_searches': []
    }

    def _mocked_saved_searches(*args, **kwargs):
        return data['saved_searches']

    data['saved_searches'] = ["minimal_metrics", "full_metrics"]

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "saved_searches", _mocked_saved_searches)


@pytest.fixture
def config_search_full_failure(config,  # type: any
                               init_config,  # type: any
                               saved_search_config,  # type: any
                               splunk_instance_basic_auth  # type: SplunkConfigInstance
                               ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []

    config["request_id"] = "full_metrics"
    config["audience"] = "admin"


@pytest.fixture
def patch_search_full_failure(monkeypatch,  # type: any
                              ):  # type: (...) -> None
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


@pytest.fixture
def config_non_default_parameters_check(config,  # type: any
                                        init_config,  # type: any
                                        saved_search_config,  # type: any
                                        splunk_instance_basic_auth  # type: SplunkConfigInstance
                                        ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []

    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"
    config["parameters"] = None
    init_config["default_parameters"] = {
        "respect": "me"
    }


@pytest.fixture
def patch_non_default_parameters_check(monkeypatch,  # type: any
                                       check,  # type: SplunkMetric
                                       ):  # type: (...) -> None
    splunk_parameters = {
        "respect": "me"
    }

    def mock_auth_session_to_check_instance_config(self, committable_state):
        for saved_search in check.splunk_telemetry_instance.saved_searches.searches:
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


@pytest.fixture
def config_overwrite_default_parameters_check(config,  # type: any
                                              init_config,  # type: any
                                              saved_search_config,  # type: any
                                              splunk_instance_basic_auth  # type: SplunkConfigInstance
                                              ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = []

    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"
    config["parameters"] = {
        "respect": "me"
    }


@pytest.fixture
def patch_overwrite_default_parameters_check(monkeypatch,  # type: any
                                             check,  # type: SplunkMetric
                                             ):  # type: (...) -> None
    splunk_parameters = {
        "respect": "me"
    }

    def mock_auth_session_to_check_instance_config(self, committable_state):
        for saved_search in check.splunk_telemetry_instance.saved_searches.searches:
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


@pytest.fixture
def config_max_query_chunk_sec_live_check(config,  # type: any
                                          init_config,  # type: any
                                          saved_search_config,  # type: any
                                          splunk_instance_basic_auth  # type: SplunkConfigInstance
                                          ):  # type: (...) -> None
    splunk_instance_basic_auth.tags = ["checktag:checktagvalue"]
    config["override_config_name"] = "metrics"
    config["request_id"] = "minimal_metrics"
    config["audience"] = "admin"

    saved_search_config["max_query_chunk_seconds"] = 300
    saved_search_config["unique_key_fields"] = None

    init_config["default_restart_history_time_seconds"] = 3600
    init_config["default_max_query_chunk_seconds"] = 300
    init_config["unique_key_fields"] = None


@pytest.fixture
def patch_max_query_chunk_sec_live_check(monkeypatch,  # type: any
                                         ):  # type: (...) -> None

    def mock_dispatch_saved_search_dispatch(*args, **kwargs):
        return "minimal_metrics"

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SplunkClient, "dispatch", mock_dispatch_saved_search_dispatch)


@pytest.fixture
def config_token_auth_with_valid_token_check(config,  # type: any
                                             init_config,  # type: any
                                             saved_search_config,  # type: any
                                             splunk_instance_token_auth  # type: SplunkConfigInstance
                                             ):  # type: (...) -> None
    config["request_id"] = "minimal_metrics"
    config["audience"] = "api-admin"


@pytest.fixture
def config_authentication_invalid_token_check(config,  # type: any
                                              init_config,  # type: any
                                              saved_search_config,  # type: any
                                              splunk_instance_token_auth  # type: SplunkConfigInstance
                                              ):  # type: (...) -> None
    config["request_id"] = "minimal_metrics"
    config["audience"] = "api-admin"

    # Forcefully create a token with an expiry time from the past
    token_expire_time = datetime.now() - timedelta(days=999)
    splunk_instance_token_auth.authentication.token_auth.initial_token = generate_mock_token(token_expire_time)


@pytest.fixture
def config_authentication_token_no_audience_parameter_check(config,  # type: any
                                                            init_config,  # type: any
                                                            saved_search_config,  # type: any
                                                            splunk_instance_token_auth  # type: SplunkConfigInstance
                                                            ):  # type: (...) -> None
    config["request_id"] = "minimal_metrics"
    config["audience"] = "api-admin"

    del splunk_instance_token_auth.authentication.token_auth.audience


@pytest.fixture
def config_authentication_token_no_name_parameter_check(config,  # type: any
                                                        init_config,  # type: any
                                                        saved_search_config,  # type: any
                                                        splunk_instance_token_auth  # type: SplunkConfigInstance
                                                        ):  # type: (...) -> None
    config["request_id"] = "minimal_metrics"
    config["audience"] = "api-admin"

    del splunk_instance_token_auth.authentication.token_auth.name
    splunk_instance_token_auth.authentication.token_auth.audience = "search"


@pytest.fixture
def config_authentication_prefer_token_over_basic_check(config,  # type: any
                                                        init_config,  # type: any
                                                        saved_search_config,  # type: any
                                                        splunk_instance_basic_auth,  # type: SplunkConfigInstance
                                                        splunk_instance_token_auth  # type: SplunkConfigInstance
                                                        ):  # type: (...) -> None
    config["request_id"] = "minimal_metrics"
    config["audience"] = "api-admin"

    splunk_instance_basic_auth.authentication.token_auth = splunk_instance_token_auth.authentication.token_auth


@pytest.fixture
def config_authentication_token_expired_check(config,  # type: any
                                              init_config,  # type: any
                                              saved_search_config,  # type: any
                                              splunk_instance_token_auth  # type: SplunkConfigInstance
                                              ):  # type: (...) -> None
    config["request_id"] = "minimal_metrics"
    config["audience"] = "api-admin"

    # Forcefully create a token with an expiry time from the past
    token_expire_time = datetime.now() - timedelta(days=999)
    splunk_instance_token_auth.authentication.token_auth.initial_token = generate_mock_token(token_expire_time)


@pytest.fixture
def config_respect_parallel_dispatches(config,  # type: any
                                       init_config,  # type: any
                                       saved_search_config,  # type: any
                                       splunk_instance_basic_auth  # type: SplunkConfigInstance
                                       ):  # type: (...) -> None

    saved_searches_parallel = 2

    splunk_instance_basic_auth.saved_searches_parallel = saved_searches_parallel

    config["request_id"] = 'savedsearch1'
    config["audience"] = "admin"
    config["ignore_search"] = True

    for request_id in ['savedsearch2', 'savedsearch3', 'savedsearch4']:
        config["mock_alternative_routes"] = [
            {
                "request_id": request_id,
                "audience": "admin",
                "ignore_search": True
            }
        ]

    splunk_instance_basic_auth.tags = []
    splunk_instance_basic_auth.saved_searches = []
    config["merge_saved_search"] = []

    for name in ['savedsearch2', 'savedsearch3', 'savedsearch4']:
        config["merge_saved_search"].append(
            SplunkConfigSavedSearchDefault({
                "name": name,
                "parameters": {},
            })
        )


@pytest.fixture
def patch_respect_parallel_dispatches(monkeypatch,  # type: any
                                      check
                                      ):  # type: (...) -> None
    def _mock_dispatch_and_await_search(self, process_data, service_check, log, persisted_state, saved_searches):
        assert len(saved_searches) == 2, \
            "Did not respect the configured saved_searches_parallel setting, got value: %i" % len(saved_searches)

        if len(saved_searches) != 2:
            check.parallel_dispatches_failed = True

        for saved_search in saved_searches:
            if saved_search.name != "savedsearch%i" % check.expected_sid_increment:
                check.parallel_dispatches_failed = True

            check.expected_sid_increment += 1
        return True

    # Monkey Patches for Mock Functions
    monkeypatch.setattr(SavedSearchesTelemetry, "_dispatch_and_await_search", _mock_dispatch_and_await_search)

    check.expected_sid_increment = 1
    check.parallel_dispatches_failed = False


def max_query_chunk_sec_history_check(monkeypatch,  # type: any
                                      get_logger,  # type: logging.Logger
                                      requests_mock,  # type: Mocker
                                      splunk_config,  # type: SplunkConfig
                                      splunk_instance_basic_auth,  # type: SplunkConfigInstance
                                      splunk_metric  # type: Type[SplunkMetric]
                                      ):  # type: (...) -> Tuple[SplunkMetric, Dict[str, any]]

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


def _connect_to_splunk():  # type: () -> None
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
            DEFAULT_SETTINGS
        )
    ).auth_session({})


@pytest.fixture(scope='session')
def test_environment():  # type: () -> Generator
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
def sts_environment(test_environment  # type: Generator
                    ):  # type: (...) -> Dict
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
def metric_integration_test_instance():  # type: () -> Dict
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
            "initial_history_time_seconds": 300
        }],
        'collection_interval': 15
    }


def _make_event_fixture(url,  # type: str
                        user,  # type: str
                        password  # type: str
                        ):  # type: (...) -> str
    """
    Send requests to a Splunk instance for creating `test_events` search.
    The Splunk started with Docker Compose command when we run integration tests.
    """
    source_type = "sts_test_data"
    saved_search = "metrics"
    metric_values = range(10)

    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (url, saved_search), auth=(user, password))

    requests.post("%s/services/saved/searches" % url,
                  data={"name": saved_search,
                        "search": 'sourcetype="{}" '
                                  'AND topo_type="{}" '
                                  'AND value!="" '
                                  'AND metric!="" '
                                  '| table _bkt _cd _time metric value host'.format(source_type, saved_search)},
                  auth=(user, password)).raise_for_status()
    for value in metric_values:
        requests.post("%s/services/receivers/simple" % url,
                      params={"host": "server_1", "sourcetype": source_type},
                      json={"topo_type": saved_search, "metric": "raw.metric", "value": value, "qa": "splunk"},
                      auth=(USER, PASSWORD)).raise_for_status()

    return saved_search
