import os
from unittest.mock import patch

import pytest
from requests_mock import Mocker

from stackstate_checks.dynatrace.dynatrace_client import DynatraceClientFactory, _DynatraceClient
from .conftest import get_fake_jwt, set_jwt_mock


@pytest.fixture
def client_args():
    return {
        "instance_name": "https://instance.live.dynatrace.com",
        "token": "original_token"
    }


def test_jwt_auth_enabled(client_args, requests_mock: Mocker):
    """
    Test that the DynatraceClientFactory correctly uses MsJWTAuth when JWT_AUTH is enabled.
    """
    set_jwt_mock(requests_mock)

    # Set environment variables directly
    os.environ["JWT_AUTH"] = "true"
    os.environ["CLIENT_ID"] = "test"
    os.environ["CLIENT_SECRET"] = "test"
    os.environ["SCOPE"] = "test"
    os.environ["TENANT_ID"] = "test-tenant-id"
    fjwt = get_fake_jwt()
    with patch.dict(os.environ, {"JWT_AUTH": "true",
                                 "CLIENT_ID": "test",
                                 "CLIENT_SECRET": "test",
                                 "SCOPE": "test"}):
        factory = DynatraceClientFactory()
        client = factory.create_client(**client_args)

        assert client is not None
        assert isinstance(client, _DynatraceClient)
        assert client.token == fjwt

    # Clean up environment variables
    for key in ["JWT_AUTH", "CLIENT_ID", "CLIENT_SECRET", "SCOPE", "TENANT_ID"]:
        if key in os.environ:
            del os.environ[key]


def test_jwt_auth_disabled(client_args):
    """
    Test that the DynatraceClientFactory uses the original token when JWT_AUTH is disabled.
    """
    with patch.dict(os.environ, {"JWT_AUTH": "false"}):
        factory = DynatraceClientFactory()
        client = factory.create_client(**client_args)

        assert client is not None
        assert isinstance(client, _DynatraceClient)
        assert client.token == "original_token"
