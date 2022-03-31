# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time


class DatadogAgentStub(object):
    """
    This implements the methods defined by the Agent's
    [C bindings](https://github.com/DataDog/datadog-agent/blob/master/rtloader/common/builtins/datadog_agent.c)
    which in turn call the
    [Go backend](https://github.com/DataDog/datadog-agent/blob/master/pkg/collector/python/datadog_agent.go).
    It also provides utility methods for test assertions.
    """

    def __init__(self):
        self._cache = {}
        self._config = self.get_default_config()
        self._hostname = 'stubbed.hostname'

    @staticmethod
    def get_default_config():
        return {'enable_metadata_collection': True, 'disable_unsafe_yaml': True}

    def reset(self):
        self._cache.clear()

    def get_hostname(self):
        return self._hostname

    def set_hostname(self, hostname):
        self._hostname = hostname

    def reset_hostname(self):
        self._hostname = 'stubbed.hostname'

    def get_config(self, config_option):
        return self._config.get(config_option, '')

    def get_version(self):
        return '0.0.0'

    def log(self, *args, **kwargs):
        pass

    def write_persistent_cache(self, key, value):
        self._cache[key] = value

    def read_persistent_cache(self, key):
        return self._cache.get(key, '')

    def warning(self, msg, *args, **kwargs):
        pass

    def error(self, msg, *args, **kwargs):
        pass

    def debug(self, msg, *args, **kwargs):
        pass

    @staticmethod
    def get_clustername():
        return 'stubbed-cluster-name'

    @staticmethod
    def get_pid():
        return 1

    @staticmethod
    def get_create_time():
        return int(1234567890)


# Use the stub as a singleton
datadog_agent = DatadogAgentStub()
