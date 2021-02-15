# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest

from stackstate_checks.base.stubs import aggregator
from stackstate_checks.dynatrace_event import DynatraceEventCheck


@pytest.fixture(scope='session')
def sts_environment():
    #  This conf instance is used when running `checksdev env start mycheck myenv`.
    #  The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    #  If you want to run an environment this object can not be empty.
    return {
        "url": "https://instance.live.dynatrace.com",
        "token": "some_token"
    }


@pytest.fixture(scope='class')
def instance():
    return {
        "url": "https://instance.live.dynatrace.com",
        "token": "some_token",
        "events_process_limit": 10
    }


@pytest.fixture
def check(instance):
    check = DynatraceEventCheck('dynatrace_event', {}, instances=[instance])
    yield check
    aggregator.reset()
    check.commit_state(None)
