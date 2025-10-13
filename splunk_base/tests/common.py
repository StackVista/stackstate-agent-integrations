# (C) SUSE 2025
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.dev import get_docker_hostname
from stackstate_checks.splunk.config import AuthType
from stackstate_checks.splunk.config.splunk_instance_config_models import SplunkConfigBasicAuthStructure, \
    SplunkConfigTokenAuthStructure, SplunkConfigTokenAuthMSStructure

HOST = get_docker_hostname()
PORT = '8089'
USER = 'admin'
PASSWORD = 'admin12345'

# For a connection to be upgraded to a JWT powered one, Splunk's KV store
# must be ready to accept connections. Sometimes this is not the case, so
# we have to wait for a number of seconds.
JWT_UPGRADE_WAIT_TIME = 60

empty_instance = {
    'url': 'https://%s:%s' % (HOST, PORT),
    'authentication': {
        'basic_auth': {
            'username': USER,
            'password': PASSWORD
        },
    },
    'saved_searches': [],
    'collection_interval': 15
}

default_settings = {
    'default_request_timeout_seconds': 5,
    'default_search_max_retry_count': 3,
    'default_search_seconds_between_retries': 1,
    'default_verify_ssl_certificate': False,
    'default_batch_size': 1000,
    'default_saved_searches_parallel': 3,
    'default_app': "search",
    'default_parameters': {
        "force_dispatch": True,
        "dispatch.now": True
    }
}


def empty_instance_jwt(initial_token):
    return {
        'url': 'https://%s:%s' % (HOST, PORT),
        'authentication': {
            'basic_auth': {
                'username': USER,
                'password': PASSWORD
            },
            'token_auth': {
                'audience': 'testing',
                'token_expiration_days': 90,
                'renewal_days': 90,
                'name': 'admin',
                'initial_token': initial_token
            },
        },
        'saved_searches': [],
        'collection_interval': 15
    }


class FakeInstanceConfig(object):
    def __init__(self):
        self.base_url = 'http://testhost:8089'
        self.default_request_timeout_seconds = 10
        self.verify_ssl_certificate = False
        self.ignore_saved_search_errors = True
        self.auth_type = AuthType.BasicAuth
        self.auth_config = SplunkConfigBasicAuthStructure(username="username", password="password")


class FakeTokenInstanceConfig(object):
    def __init__(self):
        self.base_url = 'http://testhost:8089'
        self.default_request_timeout_seconds = 10
        self.verify_ssl_certificate = False
        self.ignore_saved_search_errors = True
        self.auth_type = AuthType.TokenAuth
        self.auth_config = SplunkConfigTokenAuthStructure(name="admin", audience="test", initial_token="asdfg", token_expiration_days=90, renewal_days=10)


class FakeTokenMSInstanceConfig(object):
    def __init__(self):
        self.base_url = 'http://testhost:8089'
        self.default_request_timeout_seconds = 10
        self.verify_ssl_certificate = False
        self.ignore_saved_search_errors = True
        self.auth_type = AuthType.TokenAuthMS
        self.auth_config = SplunkConfigTokenAuthMSStructure(name="admin", cert="cert", keyfile="keyfile", request_timeout_seconds=5000)


class FakeMinimalTokenMSInstanceConfig(object):
    def __init__(self):
        self.base_url = 'http://testhost:8089'
        self.default_request_timeout_seconds = 10
        self.verify_ssl_certificate = False
        self.ignore_saved_search_errors = True
        self.auth_type = AuthType.TokenAuthMS
        self.auth_config = SplunkConfigTokenAuthMSStructure(name="admin", cert=None, keyfile=None, request_timeout_seconds=5000)

