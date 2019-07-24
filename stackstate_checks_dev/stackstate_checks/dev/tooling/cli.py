# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

import click

from .commands import ALL_COMMANDS
from .commands.console import CONTEXT_SETTINGS, echo_success, echo_waiting, echo_warning
from .config import CONFIG_FILE, config_file_exists, load_config, restore_config
from .constants import set_root
from ..compat import PermissionError
from ..utils import dir_exists


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option('--integrations', '-i', help='Work on `stackstate-agent-integrations`.')
@click.option('--core', '-c', is_flag=True, help='Work on `stackstate-agent`.')
@click.option('--here', '-x', is_flag=True, help='Work on the current location.')
@click.option('--quiet', '-q', is_flag=True)
@click.version_option()
@click.pass_context
def checksdev(ctx, integrations, core, here, quiet):
    if not quiet and not config_file_exists():
        echo_waiting(
            'No config file found, creating one with default settings now...'
        )

        try:
            restore_config()
            echo_success('Success! Please see `checksdev config`.')
        except (IOError, OSError, PermissionError):
            echo_warning(
                'Unable to create config file located at `{}`. '
                'Please check your permissions.'.format(CONFIG_FILE)
            )

    # Load and store configuration for sub-commands.
    config = load_config()

    ctx.obj = config

    root = os.path.expanduser(core if core else config.get('integrations', integrations))
    if here or not dir_exists(root):
        if not here and not quiet:
            echo_warning(
                'directory `{}` does not exist, defaulting '
                'to the current location.'.format(root)
            )
        root = os.getcwd()

    set_root(root)

    if not ctx.invoked_subcommand:
        click.echo(ctx.get_help())


for command in ALL_COMMANDS:
    checksdev.add_command(command)
