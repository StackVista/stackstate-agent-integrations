# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import os
import re
from base64 import urlsafe_b64encode

import pytest

from .._env import E2E_FIXTURE_NAME, TESTING_PLUGIN, e2e_active, get_env_vars, e2e_testing, E2E_PARENT_PYTHON, \
    format_config, AGENT_COLLECTOR_SEPARATOR, replay_check_run

try:
    from stackstate_checks.base.stubs import aggregator as __aggregator

    @pytest.fixture
    def aggregator():
        """This fixture returns a mocked Agent aggregator with state cleared."""
        __aggregator.reset()
        return __aggregator

except ImportError:
    __aggregator = None

    @pytest.fixture
    def aggregator():
        raise ImportError('stackstate-checks-base is not installed!')

try:
    from stackstate_checks.base.stubs import topology as __topology

    @pytest.fixture
    def topology():
        """This fixture returns a mocked Agent topology with state cleared."""
        __topology.reset()
        return __topology

except ImportError:
    __topology = None

    @pytest.fixture
    def topology():
        raise ImportError('stackstate-checks-base is not installed!')


@pytest.fixture(scope='session', autouse=True)
def sts_environment_runner(request):
    testing_plugin = os.getenv(TESTING_PLUGIN) == 'true'

    # Do nothing if no e2e action is triggered and continue with tests
    if not testing_plugin and not e2e_active():  # no cov
        return

    try:
        config = request.getfixturevalue(E2E_FIXTURE_NAME)
    except Exception as e:
        # pytest doesn't export this exception class so we have to do some introspection
        if e.__class__.__name__ == 'FixtureLookupError':
            # Make it explicit for our command
            pytest.exit('NO E2E FIXTURE AVAILABLE')

        raise

    metadata = {}

    # Environment fixture also returned some metadata
    if isinstance(config, tuple):
        config, possible_metadata = config

        # Support only defining the env_type for ease-of-use
        if isinstance(possible_metadata, str):
            metadata['env_type'] = possible_metadata
        else:
            metadata.update(possible_metadata)

    # Default to Docker as that is the most common
    metadata.setdefault('env_type', 'docker')

    # Save any environment variables
    metadata.setdefault('env_vars', {})
    metadata['env_vars'].update(get_env_vars(raw=True))

    data = {
        'config': config,
        'metadata': metadata,
    }

    # Serialize to json
    data = json.dumps(data, separators=(',', ':'))

    # Using base64 ensures:
    # 1. Printing to stdout won't fail
    # 2. Easy parsing since there are no spaces
    message = urlsafe_b64encode(data.encode('utf-8'))

    message = 'STSDEV_E2E_START_MESSAGE {} STSDEV_E2E_END_MESSAGE'.format(message.decode('utf-8'))

    if testing_plugin:
        return message
    else:  # no cov
        # Exit testing and pass data back up to command
        pytest.exit(message)


@pytest.fixture
def sts_agent_check(request, aggregator):
    if not e2e_testing():
        pytest.skip('Not running E2E tests')

    # Lazily import to reduce plugin load times for everyone
    from stackstate_checks.dev import TempDir, run_command

    def run_check(config=None, **kwargs):
        root = os.path.dirname(request.module.__file__)
        while True:
            if os.path.isfile(os.path.join(root, 'setup.py')):
                check = os.path.basename(root)
                break

            new_root = os.path.dirname(root)
            if new_root == root:
                raise OSError('No Datadog Agent check found')

            root = new_root

        python_path = os.environ[E2E_PARENT_PYTHON]
        env = os.environ['TOX_ENV_NAME']

        check_command = [python_path, '-m', 'datadog_checks.dev', 'env', 'check', check, env, '--json']

        if config:
            config = format_config(config)
            config_file = os.path.join(temp_dir, '{}-{}-{}.json'.format(check, env, urlsafe_b64encode(os.urandom(6))))

            with open(config_file, 'wb') as f:
                output = json.dumps(config).encode('utf-8')
                f.write(output)
            check_command.extend(['--config', config_file])

        for key, value in kwargs.items():
            if value is not False:
                check_command.append('--{}'.format(key.replace('_', '-')))

                if value is not True:
                    check_command.append(str(value))

        result = run_command(check_command, capture=True)

        matches = re.findall(AGENT_COLLECTOR_SEPARATOR + r'\n(.*?\n(?:\} \]|\]))', result.stdout, re.DOTALL)

        if not matches:
            raise ValueError(
                '{}{}\nCould not find `{}` in the output'.format(
                    result.stdout, result.stderr, AGENT_COLLECTOR_SEPARATOR
                )
            )

        for raw_json in matches:
            try:
                collector = json.loads(raw_json)
            except Exception as e:
                raise Exception("Error loading json: {}\nCollector Json Output:\n{}".format(e, raw_json))

            replay_check_run(collector, aggregator)

        return aggregator

    # Give an explicit name so we don't shadow other uses
    with TempDir('dd_agent_check') as temp_dir:
        yield run_check
