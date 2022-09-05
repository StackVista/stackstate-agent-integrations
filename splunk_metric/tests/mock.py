# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import os
import json
import jwt

from datetime import datetime, timedelta
from .common import HOST, PORT
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk_metric.splunk_metric import SplunkMetric
from stackstate_checks.splunk.telemetry.splunk_telemetry import SplunkTelemetryInstance
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.saved_search_helper import SavedSearchesTelemetry
from stackstate_checks.base.utils.common import read_file
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigInstance
from stackstate_checks.splunk.client.splunk_client import FinalizeException


def mock_finalize_sid_exception(*args, **kwargs):
    raise FinalizeException(None, "Error occurred")


def mock_search(search_id, saved_search):  # type: (str, any) -> list[str]
    if search_id == "exception":
        raise CheckException("maximum retries reached for saved search " + str(saved_search.name))

    fixture_dir = os.path.join(os.path.dirname(__file__), 'ci', 'fixtures')
    file_content = read_file("%s.json" % saved_search.name, fixture_dir)
    file_content_unmarshalled = json.loads(file_content)

    return [file_content_unmarshalled]


def mock_polling_search(*args, **kwargs):  # type: (any, any) -> list[str]
    sid = args[0]
    count = args[1].batch_size

    fixture_dir = os.path.join(os.path.dirname(__file__), 'ci', 'fixtures')
    file_content = read_file("batch_%s_seq_%s.json" % (sid, count), fixture_dir)
    file_content_unmarshalled = json.loads(file_content)

    return file_content_unmarshalled


class MockedSavedSearchesTelemetry(SavedSearchesTelemetry):
    mocks = dict()

    def __init__(self, instance_config, splunk_client, saved_searches):
        if "_dispatch_saved_search" in self.mocks:
            self._dispatch_saved_search = self.mocks.get("_dispatch_saved_search")

        if "_dispatch_and_await_search" in self.mocks:
            self._dispatch_and_await_search = self.mocks.get("_dispatch_and_await_search")

        super(MockedSavedSearchesTelemetry, self).__init__(instance_config, splunk_client, saved_searches)


class MockSplunkClient(SplunkClient):
    mocks = dict()

    def __init__(self, instance_config, *args, **kwargs):
        if "finalize_sid" in self.mocks:
            self.finalize_sid = self.mocks.get("finalize_sid")

        if "dispatch" in self.mocks:
            self.dispatch = self.mocks.get("dispatch")

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

        super(MockSplunkMetric, self).__init__(name, init_config, agent_config, instances)

    def _build_instance(self, current_time, instance, metric_instance_config, _create_saved_search):
        # type: (int, SplunkConfigInstance, any, any) -> MockSplunkTelemetryInstance
        mocked_saved_search = MockedSavedSearchesTelemetry
        mocked_saved_search.mocks = self.mocks

        mocked_splink_telemetry_instance = MockSplunkTelemetryInstance
        mocked_splink_telemetry_instance.mocks = self.mocks

        return mocked_splink_telemetry_instance(current_time, instance, metric_instance_config, _create_saved_search)


def _generate_mock_token(expire_time):
    key = 'super-secret'
    payload = {"exp": expire_time}
    return jwt.encode(payload, key, algorithm='HS512')


def _request_mock_post_token_authentication(requests_mock, logger):
    url = "http://%s:%s/services/authorization/tokens?output_mode=json" % (HOST, PORT)
    logger.debug("Mocking POST request URL for Token Authentication: %s" % url)

    token_expire_time = datetime.now() + timedelta(days=100)

    token_response = {
        "entry": [
            {
                "name": "tokens",
                "id": "https://shc-api-p1.splunk.prd.ss.aws.insim.biz/services/authorization/tokens/tokens",
                "updated": "1970-01-01T01:00:00+01:00",
                "links": {
                    "alternate": "/services/authorization/tokens/tokens",
                    "list": "/services/authorization/tokens/tokens",
                    "edit": "/services/authorization/tokens/tokens",
                    "remove": "/services/authorization/tokens/tokens"
                },
                "author": "system",
                "content": {
                    "id": "29f344ad6f98a2370e18249a58f4acea1e6775982f102b34bec5f9ee5f9af76c",
                    "token": _generate_mock_token(token_expire_time).decode('utf-8')
                }
            }
        ]
    }

    requests_mock.post(
        url=url,
        status_code=200,
        text=json.dumps(token_response)
    )


def _request_mock_post_basic_authentication(requests_mock, logger):
    url = "http://%s:%s/services/auth/login?output_mode=json" % (HOST, PORT)
    logger.debug("Mocking POST request URL for Basic Authentication: %s" % url)

    requests_mock.post(
        url=url,
        status_code=200,
        text=json.dumps({"sessionKey": "testSessionKey123", "message": "", "code": ""})
    )


def _request_mock_get_save_searches(requests_mock, logger):
    url = "http://%s:%s/services/saved/searches?output_mode=json&count=-1" % (HOST, PORT)
    logger.debug("Mocking GET request URL for Saved Searches: %s" % url)

    # List saved searches
    requests_mock.get(
        url=url,
        status_code=200,
        text=json.dumps(
            {"entry": [{"name": "Errors in the last 24 hours"},
                       {"name": "Errors in the last hour"},
                       {"name": "test_events"}],
             "paging": {"total": 3, "perPage": 18446744073709552000, "offset": 0},
             "messages": []}
        )
    )


def _request_mock_get_search_alternative(requests_mock, request_id, logger, force_failure=False):
    url = "http://%s:%s/servicesNS/-/-/search/jobs/%s/results?output_mode=json&offset=0&count=1000" \
          % (HOST, PORT, request_id)
    logger.debug("Mocking GET request URL for Search with Alternative Request Id: %s" % url)

    if request_id is not None:
        if force_failure is True:
            _force_request_get_error(requests_mock, url)
        else:
            try:
                # Get search results for job
                requests_mock.get(
                    url=url,
                    status_code=200,
                    text=read_file("%s.json" % request_id, "ci/fixtures")
                )
            except FileNotFoundError:
                return []


def _request_mock_get_search(requests_mock, request_id, logger, force_failure=False):
    url = "http://%s:%s/servicesNS/-/-/search/jobs/" \
          "stackstate_checks.base.checks.base.metric-check-name/results?output_mode=json&offset=0&count=1000" \
          % (HOST, PORT)
    logger.debug("Mocking GET request URL for Search: %s" % url)

    if request_id is not None:
        if force_failure is True:
            _force_request_get_error(requests_mock, url)
        else:
            try:
                # Get search results for job
                requests_mock.get(
                    url=url,
                    status_code=200,
                    text=read_file("%s.json" % request_id, "ci/fixtures")
                )
            except FileNotFoundError:
                return []


def _request_mock_post_dispatch_saved_search(requests_mock, request_id, logger, audience, force_failure=False):
    url = "http://%s:%s/servicesNS/%s/search/saved/searches/%s/dispatch" % (HOST, PORT, audience, request_id)
    logger.debug("Mocking POST request URL for Dispatch Saved Search: %s" % url)

    if force_failure is True:
        _force_request_post_error(requests_mock, url)
    else:
        requests_mock.post(
            url=url,
            status_code=201,
            text=json.dumps({"sid": request_id})
        )


# TODO: Melcom - Fix this mock response
def _request_mock_post_finalize_sid(requests_mock, logger, finalize_search_id):
    url = "http://%s:%s/services/search/jobs/%s/control" % (HOST, PORT, finalize_search_id)
    logger.debug("Mocking POST request URL for Dispatch Saved Search: %s" % url)

    requests_mock.post(
        url=url,
        status_code=200,
        text=json.dumps({"sid": finalize_search_id})
    )


def _force_request_get_error(requests_mock, url):
    print("FORCE FAILURE ON URL: %s" % url)
    try:
        # Get search results for job
        requests_mock.get(
            url=url,
            status_code=200,
            text=read_file("error_response.json", "ci/fixtures")
        )
    except FileNotFoundError:
        return []


def _force_request_post_error(requests_mock, url):
    print("FORCE FAILURE ON URL: %s" % url)
    try:
        # Get search results for job
        requests_mock.post(
            url=url,
            status_code=200,
            text=read_file("error_response.json", "ci/fixtures")
        )
    except FileNotFoundError:
        return []


def _requests_mock(requests_mock, request_id, audience, logger, finalize_search_id=None, ignore_search=False,
                   force_search_failure=False, force_dispatch_search_failure=False):
    _request_mock_post_token_authentication(requests_mock, logger)
    _request_mock_post_basic_authentication(requests_mock, logger)
    _request_mock_get_save_searches(requests_mock, logger)
    _request_mock_post_dispatch_saved_search(requests_mock, request_id, logger, audience, force_dispatch_search_failure)

    if ignore_search is not True:
        _request_mock_get_search(requests_mock, request_id, logger, force_search_failure)
        _request_mock_get_search_alternative(requests_mock, request_id, logger, force_search_failure)

    if finalize_search_id:
        _request_mock_post_finalize_sid(requests_mock, logger, finalize_search_id)
