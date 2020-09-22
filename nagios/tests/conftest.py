# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os
from copy import deepcopy

import pytest
from stackstate_checks.dev import TempDir, docker_run
from .common import INSTANCE_INTEGRATION, HERE, DOCKER_NAGIOS_CONF, DOCKER_NAGIOS_LOCALHOST_CONF
from .test_nagios import get_config


@pytest.fixture(scope='session')
def sts_environment():
    mysql_conf = os.path.join(HERE, 'compose', 'nagios4', 'conf.d', 'mysql.cfg')
    with TempDir("nagios_var_log") as nagios_var_log:
        e2e_metadata = {
            'docker_volumes': [
                '{}:/opt/nagios/etc/nagios.cfg'.format(DOCKER_NAGIOS_CONF),
                '{}:/opt/nagios/etc/objects/localhost.cfg'.format(DOCKER_NAGIOS_LOCALHOST_CONF),
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
def integration_instance():
    conf_dir = os.path.join(HERE, 'compose', 'nagios4', 'conf.d')
    config, _ = get_config(
        'log_file={}\ncfg_file={}\ncfg_dir={}\n'.format(DOCKER_NAGIOS_CONF, DOCKER_NAGIOS_LOCALHOST_CONF, conf_dir))
    return config['instances'][0]


@pytest.fixture
def dummy_instance():
    return {"nagios_conf": "dummy/path/nagios.cfg"}
