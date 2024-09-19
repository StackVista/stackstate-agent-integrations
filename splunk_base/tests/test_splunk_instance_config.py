# stdlib
import textwrap
import unittest

# project
from stackstate_checks.splunk.config import AuthType, SplunkInstanceConfig
from stackstate_checks.base.errors import CheckException
from pydantic import ValidationError

mock_defaults = {
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


class TestSplunkInstanceConfig(unittest.TestCase):
    def test_check_token_auth_preferred_over_basic_auth(self):
        """
        Splunk topology check should prefer Token based authentication over Basic auth mechanism
        """
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                },
                'token_auth': {
                    'name': "api-admin",
                    'initial_token': "dsfdgfhgjhkjuyr567uhfe345ythu7y6tre456sdx",
                    'audience': "admin",
                    'renewal_days': 10
                }
            },
            'component_saved_searches': [{
                "name": "components",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        instance_config = SplunkInstanceConfig(instance, {}, mock_defaults)
        assert instance_config.auth_type == AuthType.TokenAuth

    def test_error_legacy_auth(self):
        """
        Test whether username/password without the authentication block is still accepted
        """

        instance = {
            'url': 'http://localhost:8089',
            'username': 'admin',
            'password': 'admin',
            'component_saved_searches': [{
                "name": "components",
                "parameters": {}
            }],
            'relation_saved_searches': [{
                "name": "relations",
                "parameters": {}
            }],
            'tags': ['mytag', 'mytag2']
        }

        try:
            SplunkInstanceConfig(instance, {}, mock_defaults)
            assert False
        except CheckException as e:
            assert str(e) == "Instance username/password should be configured using \"authentication.basic_auth\" \
instead of username/password on top level"

    def test_combine_old_and_new_conf(self):
        instance = {
            'url': 'http://localhost:8089',
            'username': 'admin',
            'password': 'admin',
            'authentication': {
                'basic_auth': {
                    'username': "adminNew",
                    'password': "adminNew"
                }
            },
            'component_saved_searches': [{
                "name": "components",
                "parameters": {}
            }],
            'relation_saved_searches': [{
                "name": "relations",
                "parameters": {}
            }],
            'tags': ['mytag', 'mytag2']
        }

        instance_config = SplunkInstanceConfig(instance, {}, mock_defaults)
        assert instance_config.auth_type == AuthType.BasicAuth
        assert instance_config.username == "adminNew"
        assert instance_config.password == "adminNew"

    def test_check_audience_param_not_set(self):
        """
            Splunk topology check should fail and raise exception when audience param is not set
        """

        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'token_auth': {
                    'name': "admin",
                    'initial_token': "dsfdgfhgjhkjuyr567uhfe345ythu7y6tre456sdx",
                    'renewal_days': 10
                }
            },
            'component_saved_searches': [{
                "name": "components",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        try:
            SplunkInstanceConfig(instance, {}, mock_defaults)
            assert False
        except ValidationError as e:
            assert str(e) == textwrap.dedent("""\
            1 validation error for SplunkConfigInstance
            authentication.token_auth.audience
              Field required [type=missing, input_value={'name': 'admin', 'initia...dx', \
'renewal_days': 10}, input_type=dict]
                For further information visit https://errors.pydantic.dev/2.9/v/missing""")

    def test_check_name_param_not_set(self):
        """
            Splunk topology check should fail and raise exception when name param is not set
        """

        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'token_auth': {
                    'initial_token': "dsfdgfhgjhkjuyr567uhfe345ythu7y6tre456sdx",
                    'audience': "search",
                    'renewal_days': 10
                }
            },
            'component_saved_searches': [{
                "name": "components",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        try:
            SplunkInstanceConfig(instance, {}, mock_defaults)
            assert False
        except ValidationError as e:
            assert str(e) == textwrap.dedent("""\
            1 validation error for SplunkConfigInstance
            authentication.token_auth.name
              Field required [type=missing, input_value={'initial_token': 'dsfdgf...ch', \
'renewal_days': 10}, input_type=dict]
                For further information visit https://errors.pydantic.dev/2.9/v/missing""")
