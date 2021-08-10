# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
from stackstate_checks.base.stubs import aggregator, telemetry, topology

from stackstate_checks.solarwinds import SolarWindsCheck


@pytest.fixture(scope='session')
def sts_environment():
    # This conf instance is used when running `checksdev env start mycheck myenv`.
    # The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    # If you want to run an environment this object can not be empty.
    return {"key": "value"}


@pytest.fixture
def test_instance():
    return {
        "url": "solarwinds.domain.com",
        "username": "user",
        "password": "secret",
        "solarwinds_domain": "StackState_Domain",
        "solarwinds_domain_values": ["Alkmaar Subset"],
        "min_collection_interval": 30,
    }


@pytest.fixture
def solarwinds_check(test_instance):
    check = SolarWindsCheck("solarwinds", {}, {}, instances=[test_instance])
    yield check
    aggregator.reset()
    telemetry.reset()
    topology.reset()


@pytest.fixture(scope="session")
def npm_topology():
    npm_topology = None
    return npm_topology
