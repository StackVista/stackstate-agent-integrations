# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    # This conf instance is used when running `checksdev env start mycheck myenv`. 
    # The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    # If you want to run an environment this object can not be empty. 
    return {
              "cluster_name": "sandbox-main.sandbox.stackstate.io",
              "url": "http://localhost:9090"
          }

@pytest.fixture
def instance():
    return {
              "cluster_name": "sandbox-main.sandbox.stackstate.io",
              "url": "http://localhost:9090"
          }
