import pytest

from stackstate_checks.dev import WaitFor
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config.splunk_instance_config import SplunkInstanceConfig

from common import empty_instance, default_settings


@pytest.mark.integration
@pytest.mark.usefixtures("test_environment")
def test_splunk_client_auth_basic(test_environment):
    client = SplunkClient(SplunkInstanceConfig(empty_instance, {}, default_settings))
    response = client.auth_session({})
    assert response is None
