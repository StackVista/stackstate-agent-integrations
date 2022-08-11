# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import os
import json

from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk_metric.splunk_metric import SplunkMetric
from stackstate_checks.splunk.telemetry.splunk_telemetry import SplunkTelemetryInstance
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.saved_search_helper import SavedSearches
from stackstate_checks.base.utils.common import read_file
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigInstance


def mock_auth_session(committable_state):  # type: (str) -> str
    return "sessionKey1"


def mock_finalize_sid(search_id, saved_search):  # type: (str, any) -> None
    return None


def mock_saved_searches():  # type: () -> list
    return []


def mock_search(search_id, saved_search):  # type: (str, any) -> list[str]
    if search_id == "exception":
        raise CheckException("maximum retries reached for saved search " + str(saved_search.name))

    fixture_dir = os.path.join(os.path.dirname(__file__), 'ci', 'fixtures')
    file_content = read_file("%s.json" % saved_search.name, fixture_dir)
    file_content_unmarshalled = json.loads(file_content)

    return [file_content_unmarshalled]


def mock_dispatch_saved_search(log, persisted_state, saved_search):
    return log.name


class MockedSavedSearches(SavedSearches):
    mocks = dict()

    def __init__(self, instance_config, splunk_client, saved_searches):
        if "_dispatch_saved_search" in self.mocks:
            self._dispatch_saved_search = self.mocks.get("_dispatch_saved_search")

        super(MockedSavedSearches, self).__init__(instance_config, splunk_client, saved_searches)


class MockSplunkClient(SplunkClient):
    mocks = dict()

    def __init__(self, instance_config, *args, **kwargs):
        if "auth_session" in self.mocks:
            self.auth_session = self.mocks.get("auth_session")

        if "finalize_sid" in self.mocks:
            self.finalize_sid = self.mocks.get("finalize_sid")

        if "saved_searches" in self.mocks:
            self.saved_searches = self.mocks.get("saved_searches")

        if "saved_search_results" in self.mocks:
            self.saved_search_results = self.mocks.get("saved_search_results")

        super(MockSplunkClient, self).__init__(instance_config, *args, **kwargs)


class MockSplunkTelemetryInstance(SplunkTelemetryInstance):
    mocks = dict()

    def _build_splunk_client(self):  # type: () -> MockSplunkClient
        mock_splunk_client = MockSplunkClient
        mock_splunk_client.mocks = self.mocks

        return MockSplunkClient(self.instance_config)


class MockSplunkMetric(SplunkMetric):
    mocks = dict()

    def __init__(self, name, init_config, agent_config, instances=None, mocks=None):
        if mocks is None:
            self.mocks = {}
        else:
            self.mocks = mocks

        if "_current_time_seconds" in self.mocks:
            self._current_time_seconds = self.mocks.get("_current_time_seconds")

        super(MockSplunkMetric, self).__init__(name, init_config, agent_config, instances)

    def _build_instance(self, current_time, instance, metric_instance_config, _create_saved_search):
        # type: (int, SplunkConfigInstance, any, any) -> MockSplunkTelemetryInstance
        mocked_saved_search = MockedSavedSearches
        mocked_saved_search.mocks = self.mocks

        mocked_splink_telemetry_instance = MockSplunkTelemetryInstance
        mocked_splink_telemetry_instance.mocks = self.mocks

        return mocked_splink_telemetry_instance(current_time, instance, metric_instance_config, _create_saved_search,
                                                mocked_saved_search)
