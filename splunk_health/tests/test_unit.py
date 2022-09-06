import pytest

# stdlib
import json
import os
import unittest

from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import TokenExpiredException
from stackstate_checks.splunk_health.splunk_health import SplunkHealth, Instance
from stackstate_checks.base.stubs import health, aggregator
from stackstate_checks.base import TopologyInstance, AgentCheck

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'ci', 'fixtures')


def load_fixture(fixture_file):
    with open(os.path.join(FIXTURE_DIR, fixture_file)) as f:
        return json.loads(f.read())


class MockSplunkClient(object):
    def __init__(self):
        self._dispatch_parameters = None
        self.invalid_token = False

    def auth_session(self, committable_state):
        if self.invalid_token:
            raise TokenExpiredException("Current in use authentication token is expired. Please provide a valid "
                                        "token in the YAML and restart the Agent")
        return

    def saved_searches(self):
        return []

    def saved_search_results(self, search_id, saved_search):
        if search_id == "exception":
            raise CheckException("maximum retries reached for saved search " + str(search_id))
        # sid is set to saved search name
        return [load_fixture("%s.json" % search_id)]

    def dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        if saved_search.name == "dispatch_exception":
            raise Exception("BOOM")
        self._dispatch_parameters = parameters
        return saved_search.name

    def finalize_sid(self, search_id, saved_search):
        return


class MockedInstance(Instance):
    def __init__(self, *args, **kwargs):
        super(MockedInstance, self).__init__(*args, **kwargs)

    def _build_splunk_client(self):
        return MockSplunkClient()


class MockedSplunkHealth(SplunkHealth):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkHealth, self).__init__(*args, **kwargs)

    def _build_instance(self, instance):
        return MockedInstance(instance, self.init_config)


class TestSplunkCheck(unittest.TestCase):
    CHECK_NAME = "splunk"

    instance = {
        'url': 'http://localhost:8089',
        'authentication': {
            'basic_auth': {
                'username': "admin",
                'password': "admin"
            }
        },
        'saved_searches': [],
        'collection_interval': 15
    }

    instance_key = TopologyInstance("splunk", "http://localhost:8089")

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [self.instance])
        health.reset()
        aggregator.reset()
        self.check.commit_state(None)

    def test_no_topology_defined(self):
        assert self.check.run() == ''
        health.assert_snapshot(self.check.check_id,
                               self.check.health.stream,
                               {'expiry_interval_s': 0, 'repeat_interval_s': 15},
                               {})

    def test_health_data(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "health",
                "parameters": {}
            }],
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               {'expiry_interval_s': 0, 'repeat_interval_s': 15}, {},
                               [{'checkStateId': u'disk_sda',
                                 'health': 'CLEAR',
                                 'message': u'disk sda is ok',
                                 'name': u'disk sda usage',
                                 'topologyElementIdentifier': u'component1'},
                                {'checkStateId': u'disk_sdb',
                                 'health': 'CRITICAL',
                                 'name': u'disk sdb usage',
                                 'topologyElementIdentifier': u'component2'}
                                ])

        service_checks = aggregator.service_checks(SplunkHealth.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 0)

    def test_incomplete_health(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "incomplete_health",
                "parameters": {}
            }],
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() != ''

        service_checks = aggregator.service_checks(SplunkHealth.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, AgentCheck.WARNING)
        self.assertEqual(service_checks[1].status, AgentCheck.CRITICAL)

    def test_partially_incomplete(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "partially_incomplete_health",
                "parameters": {}
            }],
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               {'expiry_interval_s': 0, 'repeat_interval_s': 15}, {},
                               [{'checkStateId': u'disk_sda',
                                 'health': 'CLEAR',
                                 'message': u'disk sda is ok',
                                 'name': u'disk sda usage',
                                 'topologyElementIdentifier': u'component1'}
                                ])

        service_checks = aggregator.service_checks(SplunkHealth.SERVICE_CHECK_NAME)

        self.assertEqual(service_checks[0].status, 1)
        self.assertEqual(service_checks[0].message,
                         "The saved search 'partially_incomplete_health' contained 1 incomplete records")

    def test_wrong_health(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "wrong_health",
                "parameters": {}
            }],
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               {'expiry_interval_s': 0, 'repeat_interval_s': 15}, {},
                               [{'checkStateId': u'disk_sda',
                                 'health': 'CLEAR',
                                 'message': u'disk sda is ok',
                                 'name': u'disk sda usage',
                                 'topologyElementIdentifier': u'component1'}
                                ])

        service_checks = aggregator.service_checks(SplunkHealth.SERVICE_CHECK_NAME)

        self.assertEqual(service_checks[0].status, 1)
        self.assertEqual(service_checks[0].message,
                         "The saved search 'wrong_health' contained 1 incomplete records")

    def test_handle_saved_search_run_error(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "dispatch_exception",
                "parameters": {}
            }],
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        assert "BOOM" in self.check.run()

        service_checks = aggregator.service_checks(SplunkHealth.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)

    def test_ignore_saved_search_run_error(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "dispatch_exception",
                "parameters": {}
            }],
            'ignore_saved_search_errors': True,
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

        service_checks = aggregator.service_checks(SplunkHealth.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)

    def test_default_parameters(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "health"
            }],
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

        assert self.check.instance_data.splunk_client._dispatch_parameters == {'dispatch.now': True,
                                                                               'force_dispatch': True,
                                                                               'output_mode': 'json'}

    def test_non_default_parameters(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "health"
            }],
            'collection_interval': 15
        }

        init_config = {
            'default_parameters': {
                'respect': 'me'
            }
        }
        self.check = MockedSplunkHealth(self.CHECK_NAME, init_config, {}, [instance])
        assert self.check.run() == ''

        assert self.check.instance_data.splunk_client._dispatch_parameters == {'respect': 'me', 'output_mode': 'json'}

    def test_non_default_parameters_override(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches': [{
                "name": "health",
                "parameters": {
                    "respect": "me"
                }
            }],
            'collection_interval': 15
        }

        init_config = {
            'default_parameters': {
                'default_should': 'be_ignore'
            }
        }
        self.check = MockedSplunkHealth(self.CHECK_NAME, init_config, {}, [instance])
        assert self.check.run() == ''

        assert self.check.instance_data.splunk_client._dispatch_parameters == {'respect': 'me', 'output_mode': 'json'}

    def test_check_valid_initial_token(self):
        """
            Splunk topology check should work with valid initial token
        """

        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'token_auth': {
                    'name': "admin",
                    'initial_token': "dsfdgfhgjhkjuyr567uhfe345ythu7y6tre456sdx",
                    'audience': "search",
                    'renewal_days': 10
                }
            },
            'saved_searches': [],
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

    def test_check_invalid_initial_token(self):
        """
            Splunk check should not work with invalid initial token and stop the check
        """
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'token_auth': {
                    'name': "admin",
                    'initial_token': "dsfdgfhgjhkjuyr567uhfe345ythu7y6tre456sdx",
                    'audience': "search",
                    'renewal_days': 10
                }
            },
            'saved_searches': [],
            'collection_interval': 15
        }

        self.check = MockedSplunkHealth(self.CHECK_NAME, {}, {}, [instance])
        # Run once to initialize
        assert self.check.run() == ''
        aggregator.reset()

        self.check.instance_data.splunk_client.invalid_token = True
        assert self.check.run() == ''

        msg = "Current in use authentication token is expired. Please provide a valid token in the YAML and restart " \
              "the Agent"

        service_checks = aggregator.service_checks(SplunkHealth.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, msg)
