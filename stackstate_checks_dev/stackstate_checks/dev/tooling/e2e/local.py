# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

from shutil import copyfile, move

from .agent import (
    FAKE_API_KEY,
    get_agent_conf_dir, get_agent_exe, get_agent_pip_install,
    get_agent_service_cmd,
    get_rate_flag
)
from .config import (
    config_file_name, locate_config_dir, locate_config_file, write_env_data, remove_env_data
)
from .platform import LINUX, MAC, WINDOWS
from ..constants import get_root
from ...utils import ON_MACOS, ON_WINDOWS, ON_LINUX, path_join, file_exists
from ...subprocess import run_command


class LocalAgentInterface(object):
    ENV_TYPE = 'local'

    def __init__(self, check, env, base_package=None, config=None, metadata=None, agent_build=None, api_key=None):
        self.check = check
        self.env = env
        self.base_package = base_package
        self.config = config or {}
        self.metadata = metadata or {}
        self.agent_build = agent_build
        self.api_key = api_key or FAKE_API_KEY

        self.config_dir = locate_config_dir(check, env)
        self.config_file = locate_config_file(check, env)
        self.config_file_name = config_file_name(self.check)

    @property
    def platform(self):
        if ON_LINUX:
            return LINUX
        elif ON_MACOS:
            return MAC
        elif ON_WINDOWS:
            return WINDOWS
        else:
            raise Exception("Unsupported OS for Local E2E")

    @property
    def agent_command(self):
        return get_agent_exe(platform=self.platform)

    def write_config(self):
        write_env_data(self.check, self.env, self.config, self.metadata)
        self.copy_config_to_local_agent()

    def remove_config(self):
        remove_env_data(self.check, self.env)
        self.remove_config_from_local_agent()

    def copy_config_to_local_agent(self):
        conf_dir = get_agent_conf_dir(self.check, self.platform)
        check_conf_file = os.path.join(conf_dir, '{}.yaml'.format(self.check))
        if not os.path.exists(conf_dir):
            os.makedirs(conf_dir)

        if file_exists(check_conf_file):
            copyfile(check_conf_file, '{}.bak'.format(check_conf_file))

        copyfile(self.config_file, check_conf_file)

    def remove_config_from_local_agent(self):
        check_conf_file = os.path.join(
            get_agent_conf_dir(self.check, self.platform),
            '{}.yaml'.format(self.check)
        )
        backup_conf_file = '{}.bak'.format(check_conf_file)
        os.remove(check_conf_file)
        if file_exists(backup_conf_file):
            move(backup_conf_file, check_conf_file)

    def run_check(self, capture=False, rate=False):
        command = '{} check {}{}'.format(
            self.agent_command,
            self.check,
            ' {}'.format(get_rate_flag()) if rate else ''
        )
        return run_command(command, capture=capture)

    def update_check(self):
        install_cmd = get_agent_pip_install(self.platform) + \
                      ['-e',  path_join(get_root(), self.check)]
        return run_command(install_cmd, capture=True, check=True)

    def update_base_package(self):
        install_cmd = get_agent_pip_install(self.platform) + \
                      ['-e', self.base_package]
        return run_command(install_cmd, capture=True, check=True)

    def update_agent(self):
        # The Local E2E assumes an Agent is already installed on the machine
        pass

    def start_agent(self):
        command = get_agent_service_cmd(self.platform, 'start')
        return run_command(command, capture=True)

    def stop_agent(self):
        command = get_agent_service_cmd(self.platform, 'stop')
        run_command(command, capture=True)
