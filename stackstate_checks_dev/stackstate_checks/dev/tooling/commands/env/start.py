# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

import click
import pyperclip
from six import string_types

from ..console import (
    CONTEXT_SETTINGS, abort, echo_failure, echo_info, echo_success, echo_waiting, echo_warning
)
from ...e2e import E2E_SUPPORTED_TYPES, derive_interface, start_environment, stop_environment
from ...testing import get_available_tox_envs
from ...utils import get_tox_file
from ....utils import dir_exists, file_exists, path_join


@click.command(
    context_settings=CONTEXT_SETTINGS,
    short_help='Start an environment'
)
@click.argument('check')
@click.argument('env')
@click.option('--agent', '-a', default='stackstate/stackstate-agent-2:latest', show_default=True,
              help='The docker image of the agent to use')
@click.option('--dev/--prod', default=True, show_default=True,
              help='Use the latest version of a check (or else what is shipped with the agent package)')
@click.option('--base', is_flag=True, help='Whether to use the latest version of the base check or what is shipped.\
 Also will install all shared libraries')
@click.option('--api-key', '-k',
              help='Set the api key. can also be picked up form the STS_API_KEY environment variable')
@click.option('--sts-url', '-u',
              help='StackState product url, can also be picked up from STS_STS_URL environment variable')
@click.option('--cluster-name', '-c',
              help='Kubernetes cluster name, can also be picked up from CLUSTER_NAME environment variable')
@click.pass_context
def start(ctx, check, env, agent, dev, base, api_key, sts_url, cluster_name):
    """Start an environment."""
    if not file_exists(get_tox_file(check)):
        abort('`{}` is not a testable check.'.format(check))

    base_package = None
    if base:
        core_dir = os.path.expanduser(ctx.obj.get('core', ''))
        if not dir_exists(core_dir):
            if core_dir:
                abort('`{}` directory does not exist.'.format(core_dir))
            else:
                abort('`core` config setting does not exist.')

        base_package = path_join(core_dir, 'stackstate_checks_base')
        if not dir_exists(base_package):
            abort('`stackstate_checks_base` directory does not exist.')

    envs = get_available_tox_envs(check, e2e_only=True)

    if env not in envs:
        echo_failure('`{}` is not an available environment.'.format(env))
        echo_info('See what is available via `checksdev env ls {}`.'.format(check))
        abort()

    api_key = api_key or ctx.obj['sts_api_key']
    if api_key is None:
        echo_warning(
            'Environment/parameter variable STS_API_KEY does not exist; a well-formatted '
            'the default API_KEY will be used instead. You can also set the API key '
            'by doing `checksdev config set sts_api_key`.'
        )

    sts_url = sts_url or ctx.obj['sts_sts_url']
    if sts_url is None:
        sts_url = "http://localhost:7077/stsAgent"
        echo_warning(
            'Environment/parameter variable STS_STS_URL does not exist;'
            ' default to {}'.format(sts_url)
        )

    cluster_name = cluster_name or ctx.obj['cluster_name']
    if cluster_name is not None:
        echo_info(
            'Kubernetes clustername has been set {}'.format(cluster_name)
        )

    echo_waiting('Setting up environment `{}`... '.format(env), nl=False)
    config, metadata, error = start_environment(check, env)
    if error:
        echo_failure('failed!')
        echo_waiting('Stopping the environment...')
        stop_environment(check, env, metadata=metadata)
        abort(error)
    echo_success('success!')

    env_type = metadata['env_type']

    # Support legacy config where agent5 and agent6 were strings
    agent_ver = ctx.obj.get('agent{}'.format(agent), agent)
    if isinstance(agent_ver, string_types):
        agent_build = agent_ver
        echo_warning(
            'Agent field missing from checksdev config, please update to the latest config, '
            'falling back to latest docker image...'
        )
    else:
        agent_build = agent_ver.get(env_type, env_type)

    interface = derive_interface(env_type)
    if interface is None:
        echo_failure('`{}` is an unsupported environment type.'.format(env_type))
        echo_waiting('Stopping the environment...')
        stop_environment(check, env, metadata=metadata)
        abort()

    if env_type not in E2E_SUPPORTED_TYPES and agent.isdigit():
        echo_failure('Configuration for default Agents are only for Docker. You must specify the full build.')
        echo_waiting('Stopping the environment...')
        stop_environment(check, env, metadata=metadata)
        abort()

    environment = interface(check, env, base_package, config, metadata, agent_build, sts_url, api_key, cluster_name)

    echo_waiting('Updating `{}`... '.format(agent_build), nl=False)
    environment.update_agent()
    echo_success('success!')

    echo_waiting('Writing configuration for `{}`... '.format(env), nl=False)
    environment.write_config()
    echo_success('success!')

    echo_waiting('Starting the Agent... ', nl=False)
    result = environment.start_agent()
    if result.code:
        click.echo()
        echo_info(result.stdout + result.stderr)
        echo_failure('An error occurred.')
        echo_waiting('Stopping the environment...')
        stop_environment(check, env, metadata=metadata)
        environment.remove_config()
        abort()
    echo_success('success!')

    if base and not dev:
        dev = True
        echo_info(
            'Will install the development version of the check too so the base package can import it (in editable mode)'
        )

    editable_warning = (
        '\nEnv will started with an editable check install for the {} package. '
        'This check will remain in an editable install after '
        'the environment is torn down. Would you like to proceed?'
    )

    if base:
        echo_waiting('Upgrading the base package to the development version... ', nl=False)
        if environment.ENV_TYPE == 'local' and not click.confirm(editable_warning.format('base')):
            echo_success('skipping')
        else:
            environment.update_base_package()
            echo_success('success!')

    if dev:
        echo_waiting('Upgrading `{}` check to the development version... '.format(check), nl=False)
        if environment.ENV_TYPE == 'local' and not click.confirm(editable_warning.format(environment.check)):
            echo_success('skipping')
        else:
            environment.update_check()
            echo_success('success!')

    if dev or base:
        echo_waiting('Restarting agent to use the customer base/check... ', nl=False)
        environment.restart_agent()

    click.echo()

    try:
        pyperclip.copy(environment.config_file)
    except Exception:
        config_message = 'Config file: '
    else:
        config_message = 'Config file (copied to your clipboard): '

    echo_success(config_message, nl=False)
    echo_info(environment.config_file)
    pyperclip.copy(environment.config_file)

    echo_success('To run this check, do: ', nl=False)
    echo_info('checksdev env check {} {}'.format(check, env))

    echo_success('To stop this check, do: ', nl=False)
    echo_info('checksdev env stop {} {}'.format(check, env))
