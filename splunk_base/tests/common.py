# (C) SUSE 2025
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.dev import get_docker_hostname

HOST = get_docker_hostname()
PORT = '8089'
USER = 'admin'
PASSWORD = 'admin12345'

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
