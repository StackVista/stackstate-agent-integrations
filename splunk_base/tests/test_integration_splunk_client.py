import pytest
import time
import logging

from copy import deepcopy

from stackstate_checks.dev import WaitFor
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import AuthType, SplunkPersistentState, SplunkSavedSearch
from stackstate_checks.splunk.config.splunk_instance_config import SplunkInstanceConfig

from common import (empty_instance, empty_instance_jwt, default_settings, DISABLED_SEARCH_NAME, match_disabled_instance,
                    name_disabled_instance, JWT_UPGRADE_WAIT_TIME)
from stackstate_checks.splunk.saved_search_helper import SavedSearches


def upgrade_to_jwt_auth(client, name):
    state = SplunkPersistentState({})
    payload = {'name': name, 'audience': 'testing', 'expires_on': "+90d"}

    client.auth_session(state)
    # Ensure Splunk's KV store is ready
    time.sleep(JWT_UPGRADE_WAIT_TIME)
    response = client._do_post('/services/authorization/tokens?output_mode=json', payload, 30)
    response_json = response.json()

    new_token = response_json.get("entry")[0].get("content").get("token")
    return new_token


@pytest.mark.integration
@pytest.mark.usefixtures("test_environment")
def test_splunk_client_auth_basic(test_environment):
    client = SplunkClient(SplunkInstanceConfig(empty_instance, {}, default_settings))
    response = client.auth_session({})
    assert response is None


@pytest.mark.integration
@pytest.mark.usefixtures("test_environment")
def test_splunk_client_saved_searches(test_environment):
    client = SplunkClient(SplunkInstanceConfig(empty_instance, {}, default_settings))
    response = client.auth_session({})
    assert response is None

    saved_searches_response = [entry["name"] for entry in client.saved_searches("search")]

    assert saved_searches_response == ['Bucket Merge Retrieve Conf Settings',
                                       'Bulk Data Move Retrieve Conf Settings',
                                       DISABLED_SEARCH_NAME,
                                       'Errors in the last 24 hours',
                                       'Errors in the last hour', 'License Usage Data Cube',
                                       'Messages by minute last 3 hours', 'Orphaned scheduled searches',
                                       'Splunk errors last 24 hours']


@pytest.mark.integration
@pytest.mark.usefixtures("test_environment")
def test_splunk_client_saved_searches_all(test_environment):
    client = SplunkClient(SplunkInstanceConfig(empty_instance, {}, default_settings))
    response = client.auth_session({})
    assert response is None

    saved_searches_response = client.saved_searches("-")

    # This includes disabled searches; count varies slightly across Splunk versions
    assert len(saved_searches_response) >= 150


@pytest.mark.integration
@pytest.mark.usefixtures("test_environment")
def test_splunk_client_saved_searches_ignore_disabled(test_environment):
    instance_config = SplunkInstanceConfig(match_disabled_instance, {}, default_settings)
    client = SplunkClient(instance_config)
    response = client.auth_session({})
    assert response is None

    searches = [SplunkSavedSearch(instance_config, saved_search_instance)
                for saved_search_instance in match_disabled_instance['saved_searches']]
    saved_searches_helper = SavedSearches(instance_config, client, searches)

    log = logging.getLogger('{}.{}'.format(__name__, "test_splunk_client_saved_searches_ignore_disabled"))

    saved_searches_helper._update_searches(log)

    assert len(saved_searches_helper.searches) == 0


@pytest.mark.integration
@pytest.mark.usefixtures("test_environment")
def test_splunk_client_saved_searches_ignore_disabled_name(test_environment):
    instance_config = SplunkInstanceConfig(name_disabled_instance, {}, default_settings)
    client = SplunkClient(instance_config)
    response = client.auth_session({})
    assert response is None

    searches = [SplunkSavedSearch(instance_config, saved_search_instance)
                for saved_search_instance in name_disabled_instance['saved_searches']]
    saved_searches_helper = SavedSearches(instance_config, client, searches)

    log = logging.getLogger('{}.{}'.format(__name__, "test_splunk_client_saved_searches_ignore_disabled"))

    saved_searches_helper._update_searches(log)

    assert len(saved_searches_helper.searches) == 0


@pytest.mark.integration
@pytest.mark.usefixtures("test_environment")
def test_splunk_client_auth_jwt(test_environment):
    config = SplunkInstanceConfig(empty_instance, {}, default_settings)
    client = SplunkClient(config)
    new_token = upgrade_to_jwt_auth(client, 'admin')

    state = SplunkPersistentState({})
    new_config = SplunkInstanceConfig(empty_instance_jwt(new_token), {}, default_settings)
    jwt_powered_client = SplunkClient(new_config)
    response = jwt_powered_client.auth_session(state)
    assert response is None
