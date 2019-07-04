# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

FAKE_API_KEY = "API_KEY"


def get_rate_flag():
    return '--check-rate'


def get_agent_exe(platform='linux'):
    if platform == 'windows':
        return ''
    elif platform == 'mac':
        return ''
    else:
        return '/opt/stackstate-agent/bin/agent/agent'


def get_agent_conf_dir(check, platform='linux'):
    if platform == 'windows':
        return ''
    elif platform == 'mac':
        return ''
    else:
        return '/etc/stackstate-agent/conf.d/{}.d'.format(check)
