# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os
from copy import deepcopy

import pytest

from stackstate_checks.dev import TempDir, docker_run
from .common import INSTANCE_INTEGRATION, HERE


@pytest.fixture(scope='session')
def sts_environment():
    nagios_conf = os.path.join(HERE, 'compose', 'nagios4', 'nagios.cfg')
    localhost_conf = os.path.join(HERE, 'compose', 'nagios4', 'localhost.cfg')
    mysql_conf = os.path.join(HERE, 'compose', 'nagios4', 'mysql.cfg')
    with TempDir("nagios_var_log") as nagios_var_log:
        e2e_metadata = {
            'docker_volumes': [
                '{}:/etc/nagios/nagios.cfg'.format(nagios_conf),
                '{}:/opt/nagios/etc/objects/localhost.cfg'.format(localhost_conf),
                '{}:/opt/nagios/etc/conf.d/mysql.cfg'.format(mysql_conf),
                '{}:/opt/nagios/var/log/'.format(nagios_var_log),
            ]
        }

        with docker_run(
                os.path.join(HERE, 'compose', 'docker-compose.yaml'),
                env_vars={'NAGIOS_LOGS_PATH': nagios_var_log},
                build=True,
        ):
            yield INSTANCE_INTEGRATION, e2e_metadata


@pytest.fixture
def instance():
    return deepcopy(INSTANCE_INTEGRATION)


@pytest.fixture
def dummy_instance():
    return {"nagios_conf": "dummy/path/nagios.cfg"}
