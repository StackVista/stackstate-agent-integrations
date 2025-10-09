# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import base64
import json
import time

from stackstate_checks.dynatrace.dynatrace_client import DynatraceClientFactory


@pytest.fixture
def test_instance():
    return {
        "url": "https://instance.live.dynatrace.com",
        "token": "some_token",
        "events_process_limit": 10,
        "events_bootstrap_days": 5,
        "timeout": 20
    }


@pytest.fixture
def dynatrace_client(test_instance):
    factory = DynatraceClientFactory()
    client = factory.create_client(instance_name=test_instance.get('url'),
                                   token=test_instance.get('token'),
                                   verify=False,
                                   cert=None,
                                   keyfile=None,
                                   timeout=10)
    return client


def set_jwt_mock(requests_mock):
    fjwt = get_fake_jwt()
    # Mock the Microsoft login response with a specific pattern
    requests_mock.post("https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token",
                       json={"access_token": fjwt, "expires_in": 3600},
                       status_code=200)


fake_jwt = ""


def get_fake_jwt():
    global fake_jwt

    if fake_jwt == "":
        # Create a valid-looking fake JWT for the mock response
        exp_time = int(time.time()) + 3600
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"exp": exp_time}
        encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
        encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
        fake_signature = base64.urlsafe_b64encode(b'fakesignature').rstrip(b'=').decode()
        fake_jwt = f"{encoded_header}.{encoded_payload}.{fake_signature}"
    return fake_jwt
