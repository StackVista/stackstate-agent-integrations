import pytest
from requests_mock import Mocker

from unittest.mock import patch

import json
import base64
import time
import os

from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import AuthType, SplunkPersistentState

from common import FakeInstanceConfig, FakeMinimalTokenMSInstanceConfig, FakeTokenMSInstanceConfig
from test_splunk_client import FakeResponse

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit


def test_static_header_with_basic_auth(requests_mock: Mocker):
    """
    Test adding a static header to the requests session
    """
    os.environ["SPLUNK_AUTH_STATIC_HEADER_NAME"] = "x-backend-auth"
    os.environ["SPLUNK_AUTH_STATIC_HEADER_VALUE"] = "Bearer token"

    instance = FakeInstanceConfig()
    helper = SplunkClient(instance)

    requests_mock.post("http://testhost:8089/services/auth/login",
                       json={"sessionKey": "MySessionKeyForThisSession"},
                       status_code=200)

    helper.auth_session({})

    expected_header = helper.requests_session.headers.get("Authentication")
    assert expected_header == "Splunk MySessionKeyForThisSession"

    expected_static_header = helper.requests_session.headers.get("x-backend-auth")
    assert expected_static_header == "Bearer token"


def test_static_header_with_token_ms(requests_mock: Mocker):
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
    os.environ["SPLUNK_AUTH_STATIC_HEADER_NAME"] = "x-backend-auth"
    os.environ["SPLUNK_AUTH_STATIC_HEADER_VALUE"] = "Bearer token"

    status = SplunkPersistentState({})

    client = SplunkClient(FakeTokenMSInstanceConfig())
    client.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})

    requests_mock.post("https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token",
                       json={"access_token": fake_jwt, "expires_in": 3600},
                       status_code=200)

    client.auth_session(status)
    assert client.requests_session.headers['Authorization'] == f"Bearer {fake_jwt}"

    expected_static_header = client.requests_session.headers.get("x-backend-auth")
    assert expected_static_header == "Bearer token"
