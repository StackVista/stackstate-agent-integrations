import pytest

# stdlib
import json
import os
import unittest

from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import TokenExpiredException
from stackstate_checks.splunk_topology.splunk_topology import SplunkTopology, Instance
from stackstate_checks.base.stubs import topology, aggregator
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


class MockedSplunkTopology(SplunkTopology):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkTopology, self).__init__(*args, **kwargs)

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
        'component_saved_searches': [],
        'relation_saved_searches': []
    }

    instance_key = TopologyInstance("splunk", "http://localhost:8089")

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [self.instance])
        topology.reset()
        aggregator.reset()
        self.check.commit_state(None)

    def test_no_topology_defined(self):
        assert self.check.run() == ''
        topology.assert_snapshot(self.check.check_id, self.instance_key, True, True)

    def test_components_and_relation_data(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
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

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''
        topology.assert_snapshot(self.check.check_id, self.instance_key, True, True,
                                 [{
                                     'id': u'vm_2_1',
                                     'type': u'vm',
                                     'data': {
                                         u"running": True,
                                         u"_time": "2017-03-06T14:55:54.000+00:00",
                                         u"label.label1Key": "label1Value",
                                         u"tags": ['integration-type:splunk',
                                                   'integration-url:http://localhost:8089',
                                                   'mytag', 'mytag2', 'result_tag1']
                                     }
                                 }, {
                                     "id": u"server_2",
                                     "type": u"server",
                                     "data": {
                                         u"description": "My important server 2",
                                         u"_time": "2017-03-06T14:55:54.000+00:00",
                                         u"label.label2Key": "label2Value",
                                         u"tags": ['integration-type:splunk',
                                                   'integration-url:http://localhost:8089',
                                                   'mytag', 'mytag2', 'result_tag2']
                                     }
                                 }],
                                 [{
                                     "type": u"HOSTED_ON",
                                     "source_id": u"vm_2_1",
                                     "target_id": u"server_2",
                                     "data": {
                                         u"description": "Some relation",
                                         u"_time": "2017-03-06T15:10:57.000+00:00",
                                         "tags": ['mytag', 'mytag2']
                                     }
                                 }])

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 0)

    def test_no_snapshot(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'snapshot': False,
            'component_saved_searches': [{
                "name": "components",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''
        topology.assert_snapshot(self.check.check_id, self.instance_key, False, False,
                                 [{
                                     'id': u'vm_2_1',
                                     'type': u'vm',
                                     'data': {
                                         u"running": True,
                                         u"_time": "2017-03-06T14:55:54.000+00:00",
                                         u"label.label1Key": "label1Value",
                                         u"tags": ['integration-type:splunk',
                                                   'integration-url:http://localhost:8089',
                                                   'mytag', 'mytag2', 'result_tag1']
                                     }
                                 }, {
                                     "id": u"server_2",
                                     "type": u"server",
                                     "data": {
                                         u"description": "My important server 2",
                                         u"_time": "2017-03-06T14:55:54.000+00:00",
                                         u"label.label2Key": "label2Value",
                                         u"tags": ['integration-type:splunk',
                                                   'integration-url:http://localhost:8089',
                                                   'mytag', 'mytag2', 'result_tag2']
                                     }
                                 }],
                                 [])

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 0)

    def test_minimal_topology(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'snapshot': True,
            'component_saved_searches': [{
                "name": "minimal_components",
                "parameters": {}
            }],
            'relation_saved_searches': [{
                "name": "minimal_relations",
                "parameters": {}
            }],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''
        topology.assert_snapshot(self.check.check_id, self.instance_key, True, True,
                                 [{"id": u"vm_2_1",
                                   "type": u"vm",
                                   "data": {
                                       u"tags": ['integration-type:splunk',
                                                 'integration-url:http://localhost:8089',
                                                 'mytag', 'mytag2']
                                   }
                                   }, {
                                      'id': u"server_2",
                                      "type": u'server',
                                      "data": {
                                          u"tags": ['integration-type:splunk',
                                                    'integration-url:http://localhost:8089',
                                                    'mytag', 'mytag2']
                                      }
                                  }],
                                 [{"type": u"HOSTED_ON",
                                   "source_id": u"vm_2_1",
                                   "target_id": u"server_2",
                                   "data": {
                                       "tags": ['mytag', 'mytag2']
                                   }}])

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 0)

    def test_incomplete_topology(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'snapshot': True,
            'component_saved_searches': [{
                "name": "incomplete_components",
                "parameters": {}
            }],
            'relation_saved_searches': [{
                "name": "mincomplete_relations",
                "parameters": {}
            }],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() != ''

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
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
            'snapshot': True,
            'component_saved_searches': [{
                "name": "partially_incomplete_components",
                "parameters": {}
            }],
            'relation_saved_searches': [{
                "name": "partially_incomplete_relations",
                "parameters": {}
            }],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''
        topology.assert_snapshot(self.check.check_id, self.instance_key, True, True,
                                 [{"id": u"vm_2_1",
                                   "type": u"vm",
                                   "data": {
                                       u"tags": ['integration-type:splunk',
                                                 'integration-url:http://localhost:8089',
                                                 'mytag', 'mytag2']
                                   }
                                   }],
                                 [{"type": u"HOSTED_ON",
                                   "source_id": u"vm_2_1",
                                   "target_id": u"server_2",
                                   "data": {
                                       "tags": ['mytag', 'mytag2']
                                   }}])

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)

        self.assertEqual(service_checks[0].status, 1)
        self.assertEqual(service_checks[0].message,
                         "The saved search 'partially_incomplete_components' contained 1 incomplete records")
        self.assertEqual(service_checks[1].status, 1)
        self.assertEqual(service_checks[1].message,
                         "The saved search 'partially_incomplete_relations' contained 1 incomplete records")

    def test_upgrade_error_default_polling_interval(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'snapshot': True,
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

        init_config = {'default_polling_interval_seconds': 15}

        self.check = MockedSplunkTopology(self.CHECK_NAME, init_config, {}, [instance])
        assert "deprecated config `init_config.default_polling_interval_seconds` found." in self.check.run()

    def test_upgrade_error_polling_interval(self):
        instance = {
            'url': 'http://localhost:8089',
            'polling_interval_seconds': 15,
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'snapshot': True,
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

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert "deprecated config `polling_interval_seconds` found." in self.check.run()

    def test_handle_saved_search_run_error(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'component_saved_searches': [{
                "name": "dispatch_exception",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert "BOOM" in self.check.run()

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
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
            'component_saved_searches': [{
                "name": "dispatch_exception",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'ignore_saved_search_errors': True,
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
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
            'component_saved_searches': [{
                "name": "components"
            }],
            'relation_saved_searches': [{
                "name": "relations"
            }]
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

        assert self.check.instance_data.splunk_client._dispatch_parameters == {'dispatch.now': True,
                                                                               'force_dispatch': True}

    def test_non_default_parameters(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'component_saved_searches': [{
                "name": "components"
            }],
            'relation_saved_searches': [{
                "name": "relations"
            }]
        }

        init_config = {
            'default_parameters': {
                'respect': 'me'
            }
        }
        self.check = MockedSplunkTopology(self.CHECK_NAME, init_config, {}, [instance])
        assert self.check.run() == ''

        assert self.check.instance_data.splunk_client._dispatch_parameters == {'respect': 'me'}

    def test_non_default_parameters_override(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'component_saved_searches': [{
                "name": "components",
                "parameters": {
                    "respect": "me"
                }
            }],
            'relation_saved_searches': [{
                "name": "relations",
                "parameters": {
                    "respect": "me"
                }
            }]
        }

        init_config = {
            'default_parameters': {
                'default_should': 'be_ignore'
            }
        }
        self.check = MockedSplunkTopology(self.CHECK_NAME, init_config, {}, [instance])
        assert self.check.run() == ''

        assert self.check.instance_data.splunk_client._dispatch_parameters == {'respect': 'me'}

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
            'component_saved_searches': [{
                "name": "components",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
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
            'component_saved_searches': [{
                "name": "components",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        # Run once to initialize
        assert self.check.run() == ''
        aggregator.reset()

        self.check.instance_data.splunk_client.invalid_token = True
        assert self.check.run() == ''

        msg = "Current in use authentication token is expired. Please provide a valid token in the YAML and restart " \
              "the Agent"

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, msg)
