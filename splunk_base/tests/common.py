# (C) SUSE 2025
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.dev import get_docker_hostname
from stackstate_checks.splunk.config import AuthType

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
        self.username = "admin"
        self.audience = "test"
        self.name = "admin"
        self.token_expiration_days = 90
        self.renewal_days = 10
        self.initial_token = "asdfg"
        self.auth_type = AuthType.BasicAuth
        self.keyfile = ""
        self.cert = ""
        self.timeout = 5000

    def get_auth_tuple(self):
        return ('username', 'password')


class FakePartialInstanceConfig(object):
    def __init__(self):
        self.base_url = 'http://testhost:8089'
        self.default_request_timeout_seconds = 10
        self.verify_ssl_certificate = False
        self.ignore_saved_search_errors = True
        self.username = "admin"
        self.audience = "test"
        self.name = "admin"
        self.token_expiration_days = 90
        self.renewal_days = 10
        self.initial_token = "asdfg"
        self.auth_type = AuthType.BasicAuth
        self.timeout = 5000

    def get_auth_tuple(self):
        return ('username', 'password')
