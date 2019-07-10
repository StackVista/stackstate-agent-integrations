# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from os.path import expanduser

from .platform import MAC, WINDOWS

FAKE_API_KEY = "API_KEY"

MANIFEST_VERSION_PATTERN = r'agent (\d)'


def get_rate_flag():
    return '--check-rate'


def get_agent_exe(platform='linux'):
    if platform == 'windows':
        return r"C:\Program Files\StackState\StackState Agent\embedded\agent.exe"
    elif platform == 'mac':
        return 'datadog-agent'
    else:
        return '/opt/stackstate-agent/bin/agent/agent'


def get_agent_conf_dir(check, platform='linux'):
    if platform == 'windows':
        return r'C:\ProgramData\StackState\conf.d\{}.d'.format(check)
    elif platform == 'mac':
        return '/opt/stackstate-agent/etc/conf.d/{}.d'.format(check)
    else:
        return '/etc/stackstate-agent/conf.d/{}.d'.format(check)


def get_agent_version_manifest(platform):
    if platform == WINDOWS:
        return r'C:\Program Files\StackState\StackState Agent\version-manifest.txt'
    else:
        return '/opt/stackstate-agent/version-manifest.txt'


def get_agent_pip_install(platform):
    if platform == WINDOWS:
        return [r'C:\Program Files\StackState\StackState Agent\embedded\python', '-m', 'pip', 'install']
    else:
        return ['/opt/stackstate-agent/embedded/bin/pip', 'install', '--user']


def get_agent_service_cmd(platform, action):
    if platform == WINDOWS:
        arg = 'start-service' if action == 'start' else 'stopservice'
        return (
            r'powershell -executionpolicy bypass -Command Start-Process """""""""C:\Program Files\StackState\StackState'
            r' Agent\embedded\agent.exe""""""""" -Verb runAs -argumentlist {}'.format(arg)
        )
    elif platform == MAC:
        return [
            'launchctl', 'load' if action == 'start' else 'unload', '-w',
            '{}/Library/LaunchAgents/com.stackstate.agent.plist'.format(expanduser("~"))
        ]
    else:
        return ['sudo', 'service', 'stackstate-agent', action]
