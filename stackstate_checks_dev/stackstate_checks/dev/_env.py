# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

E2E_FIXTURE_NAME = 'sts_environment'
E2E_SET_UP = 'STSDEV_E2E_UP'
E2E_TEAR_DOWN = 'STSDEV_E2E_DOWN'
TESTING_PLUGIN = 'STSDEV_TESTING_PLUGIN'


def set_up_env():
    return os.getenv(E2E_SET_UP, 'true') != 'false'


def tear_down_env():
    return os.getenv(E2E_TEAR_DOWN, 'true') != 'false'
