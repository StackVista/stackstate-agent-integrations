import os
from unittest.mock import patch
import base64
import json
import time

import pytest
from requests_mock import Mocker

from stackstate_checks.dynatrace.dynatrace_client import DynatraceClientFactory, _DynatraceClient


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
    # Create a valid-looking fake JWT for the mock response
    exp_time = int(time.time()) + 3600
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"exp": exp_time}
    encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    fake_signature = base64.urlsafe_b64encode(b'fakesignature').rstrip(b'=').decode()
    fake_jwt = f"{encoded_header}.{encoded_payload}.{fake_signature}"

    # Mock the Microsoft login response
    requests_mock.post("https://login.microsoftonline.com/None/oauth2/v2.0/token",
                       json={"access_token": fake_jwt, "expires_in": 3600})

    with patch.dict(os.environ, {"JWT_AUTH": "true", "CLIENT_ID": "test", "CLIENT_SECRET": "test", "SCOPE": "test"}):
        factory = DynatraceClientFactory()
        client = factory.create_client(**client_args)

        assert client is not None
        assert isinstance(client, _DynatraceClient)
        assert client.token == fake_jwt


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
