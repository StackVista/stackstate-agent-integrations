# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import click

from .config import config
from .dep import dep
from .manifest import manifest
from .metadata import metadata
from .service_checks import service_checks
from .py3 import py3
from ..console import CONTEXT_SETTINGS

ALL_COMMANDS = (
    config,
    dep,
    manifest,
    metadata,
    py3,
    service_checks,
)

@click.group(
    context_settings=CONTEXT_SETTINGS,
    short_help='Verify certain aspects of the repo'
)
def validate():
    pass


for command in ALL_COMMANDS:
    validate.add_command(command)
