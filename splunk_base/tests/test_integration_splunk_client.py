import pytest
import time

from copy import deepcopy

from stackstate_checks.dev import WaitFor
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import AuthType, SplunkPersistentState
from stackstate_checks.splunk.config.splunk_instance_config import SplunkInstanceConfig

from common import empty_instance, empty_instance_jwt, default_settings


def upgrade_to_jwt_auth(client, name):
    state = SplunkPersistentState({})
    payload = {'name': name, 'audience': 'testing', 'expires_on': "+90d"}

    client.auth_session(state)
    # Ensure Splunk's KV store is ready
    time.sleep(10)
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
def test_splunk_client_auth_jwt(test_environment):
    config = SplunkInstanceConfig(empty_instance, {}, default_settings)
    client = SplunkClient(config)
    new_token = upgrade_to_jwt_auth(client, 'admin')

    state = SplunkPersistentState({})
    new_config = SplunkInstanceConfig(empty_instance_jwt(new_token), {}, default_settings)
    jwt_powered_client = SplunkClient(new_config)
    response = jwt_powered_client.auth_session(state)
    assert response is None
