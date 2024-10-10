# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest

from stackstate_checks.dynatrace.dynatrace_client import DynatraceClient


@pytest.fixture
def test_instance():
    return {
        "url": "https://instance.live.dynatrace.com",
        "token": "some_token",
        "events_process_limit": 10,
        "events_boostrap_days": 5,
        "timeout": 20
    }


@pytest.fixture
def dynatrace_client(test_instance):
    client = DynatraceClient(token=test_instance.get('token'),
                             verify=False,
                             cert=None,
                             keyfile=None,
                             timeout=10)
    return client
