import pytest
from requests_mock import Mocker

from unittest.mock import patch

import json
import base64
import datetime
import time
import os

from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import AuthType, SplunkPersistentState

from common import FakeInstanceConfig, FakeMinimalTokenMSInstanceConfig, FakeTokenMSInstanceConfig

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit


def test_jwt_adapter_msft_client(requests_mock: Mocker):
    """
    Test JWT adapter Microsoft AD JWT client
    """
    # Create a valid-looking fake JWT for the mock response
    exp_time = int(time.time()) + 3600
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"exp": exp_time}
    encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    fake_signature = base64.urlsafe_b64encode(b'fakesignature').rstrip(b'=').decode()
    fake_jwt = f"{encoded_header}.{encoded_payload}.{fake_signature}"

    os.environ["CLIENT_ID"] = "test"
    os.environ["CLIENT_SECRET"] = "test"
    os.environ["SCOPE"] = "test"
    os.environ["TENANT_ID"] = "test-tenant-id"

    status = SplunkPersistentState({})

    client = SplunkClient(FakeTokenMSInstanceConfig())
    client.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})

    requests_mock.post("https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token",
                       json={"access_token": fake_jwt, "expires_in": 3600},
                       status_code=200)

    with patch.dict(os.environ, {"JWT_AUTH": "true", "CLIENT_ID": "test", "CLIENT_SECRET": "test", "SCOPE": "test"}):
        client.auth_session(status)
        assert client.requests_session.headers['Authorization'] == f"Bearer {fake_jwt}"


def test_jwt_adapter_msft_client_partial_config(requests_mock: Mocker):
    """
    Test JWT adapter Microsoft AD JWT client
    """
    # Create a valid-looking fake JWT for the mock response
    exp_time = int(time.time()) + 3600
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"exp": exp_time}
    encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    fake_signature = base64.urlsafe_b64encode(b'fakesignature').rstrip(b'=').decode()
    fake_jwt = f"{encoded_header}.{encoded_payload}.{fake_signature}"

    os.environ["CLIENT_ID"] = "test"
    os.environ["CLIENT_SECRET"] = "test"
    os.environ["SCOPE"] = "test"
    os.environ["TENANT_ID"] = "test-tenant-id"

    status = SplunkPersistentState({})

    client = SplunkClient(FakeMinimalTokenMSInstanceConfig())
    client.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})

    requests_mock.post("https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token",
                       json={"access_token": fake_jwt, "expires_in": 3600},
                       status_code=200)

    with patch.dict(os.environ, {"JWT_AUTH": "true", "CLIENT_ID": "test", "CLIENT_SECRET": "test", "SCOPE": "test"}):
        client.auth_session(status)
        assert client.requests_session.headers['Authorization'] == f"Bearer {fake_jwt}"
