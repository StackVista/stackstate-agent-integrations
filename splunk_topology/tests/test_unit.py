import pytest

# stdlib
import json
import os
import unittest
import copy

from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import TokenExpiredException
from stackstate_checks.splunk_topology.splunk_topology import SplunkTopology
from stackstate_checks.base.stubs import topology, aggregator
from stackstate_checks.base import TopologyInstance

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'ci', 'fixtures')


def load_fixture(fixture_file):
    with open(os.path.join(FIXTURE_DIR, fixture_file)) as f:
        return json.loads(f.read())


class MockedSplunkTopology(SplunkTopology):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkTopology, self).__init__(*args, **kwargs)
        self.finalized = []
        self.saved_searches = []
        self._dispatch_parameters = None

    def _search(self, search_id, saved_search, instance):
        if search_id == "exception":
            raise CheckException("maximum retries reached for saved search " + str(search_id))
        # sid is set to saved search name
        return [load_fixture("%s.json" % search_id)]

    def _saved_searches(self, instance):
        return self.saved_searches

    def _auth_session(self, instance, status):
        return

    def _dispatch(self, instance, saved_search, splunk_app, _ignore_saved_search, parameters):
        self._dispatch_parameters = parameters
        return saved_search.name

    def _finalize_sid(self, instance, sid, saved_search):
        self.finalized.append(sid)
        return None


class MockedSplunkTopologyFinalizeException(MockedSplunkTopology):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkTopologyFinalizeException, self).__init__(*args, **kwargs)
        self.finalized = []

    def _finalize_sid(self, instance, sid, saved_search):
        self.finalized.append(sid)
        raise Exception("Finalize exception")


class MockedSplunkTopologyIncompleteAndPartialResult(MockedSplunkTopology):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkTopologyIncompleteAndPartialResult, self).__init__(*args, **kwargs)

    def _search(self, search_id, saved_search, instance):
        # sid is set to saved search name
        return [load_fixture("partially_incomplete_%s.json" % search_id),
                load_fixture("incomplete_%s.json" % search_id)]


class MockedSplunkTopologyDispatchError(MockedSplunkTopology):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkTopologyDispatchError, self).__init__(*args, **kwargs)

    def _dispatch(self, instance, saved_search, splunk_app, _ignore_saved_search, parameters):
        raise Exception("BOOM")


class MockedSplunkTopologySavedSearchesError(MockedSplunkTopology):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkTopologySavedSearchesError, self).__init__(*args, **kwargs)

    def _saved_searches(self, instance):
        raise Exception("BOOM")


class MockedSplunkTopologyCheckParallel(MockedSplunkTopology):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkTopologyCheckParallel, self).__init__(*args, **kwargs)
        self.expected_sid_increment = 1

    def _dispatch_and_await_search(self, instance, state, saved_searches):
        assert len(saved_searches) <= 2

        for saved_search in saved_searches:
            result = saved_search.name
            expected = "savedsearch%i" % self.expected_sid_increment
            assert result == expected
            self.expected_sid_increment += 1

        return True


class MockedSplunkTopologyInvalidToken(SplunkTopology):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkTopologyInvalidToken, self).__init__(*args, **kwargs)

    def _auth_session(self, instance, state):
        raise TokenExpiredException("Current in use authentication token is expired. Please provide a valid "
                                    "token in the YAML and restart the Agent")


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
        self.check.run()
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

    def test_store_and_finalize_sids(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'component_saved_searches': [{
                "name": "broken_search_result",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        # Run the check but break the search result using the 'broken_result', thiis will persist the sid
        assert self.check.run() != ''

        first_persistent_data = copy.deepcopy(self.check.state_manager.get_state(self.check._get_state_descriptor()))
        assert first_persistent_data is not None

        # Run the check 2nd time and get the persistent status data
        assert self.check.run() != ''

        second_persistent_data = copy.deepcopy(self.check.state_manager.get_state(self.check._get_state_descriptor()))

        # The second run_check will finalize the previous saved search id and create a new one,
        # so we make sure this is the case
        assert self.check.finalized == ["broken_search_result"]
        self.assertEqual(first_persistent_data, second_persistent_data)

    def test_keep_sid_when_finalize_fails(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'component_saved_searches': [{
                "name": "broken_search_result",
                "parameters": {}
            }],
            'relation_saved_searches': [],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopologyFinalizeException(self.CHECK_NAME, {}, {}, [instance])
        # Run the check but break the search result using the 'broken_result', thiis will persist the sid
        assert self.check.run() != ''

        first_persistent_data = copy.deepcopy(self.check.state_manager.get_state(self.check._get_state_descriptor()))
        assert first_persistent_data is not None

        # Run the check 2nd time and get the persistent status data, we break on the finalizer
        assert 'Finalize exception' in self.check.run()

        second_persistent_data = copy.deepcopy(self.check.state_manager.get_state(self.check._get_state_descriptor()))

        # The second run_check will finalize the previous saved search id and create a new one,
        # so we make sure this is the case
        assert self.check.finalized == ["broken_search_result"]
        self.assertEqual(first_persistent_data, second_persistent_data)

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
        self.assertEqual(service_checks[0].status, 2)

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
                         "The saved search 'partially_incomplete_components' contained 1 incomplete component records")
        self.assertEqual(service_checks[1].status, 1)
        self.assertEqual(service_checks[1].message,
                         "The saved search 'partially_incomplete_relations' contained 1 incomplete relation records")

    def test_partially_incomplete_and_incomplete(self):
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

        self.check = MockedSplunkTopologyIncompleteAndPartialResult(self.CHECK_NAME, {}, {}, [instance])
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
                         "The saved search 'components' contained 3 incomplete component records")
        self.assertEqual(service_checks[1].status, 1)
        self.assertEqual(service_checks[1].message,
                         "The saved search 'relations' contained 2 incomplete relation records")

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

    def test_handle_dispatch_error(self):
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

        self.check = MockedSplunkTopologyDispatchError(self.CHECK_NAME, {}, {}, [instance])
        assert "BOOM" in self.check.run()

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)

    def test_handle_saved_searches_error(self):
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

        self.check = MockedSplunkTopologySavedSearchesError(self.CHECK_NAME, {}, {}, [instance])
        assert "BOOM" in self.check.run()

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)

    def test_ignore_saved_searches_error(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'ignore_saved_search_errors': True,
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

        self.check = MockedSplunkTopologySavedSearchesError(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)

    def test_wildcard_topology(self):
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'component_saved_searches': [{
                "match": "comp.*",
                "parameters": {}
            }],
            'relation_saved_searches': [{
                "match": "rela.*",
                "parameters": {}
            }],
            'tags': ['mytag', 'mytag2']
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        self.check.saved_searches = ["components", "relations"]
        assert self.check.run() == ''

        self.assertEqual(len(topology.get_snapshot(self.check.check_id)['components']), 2)
        self.assertEquals(len(topology.get_snapshot(self.check.check_id)['relations']), 1)

        topology.reset()
        self.check.saved_searches = []
        assert self.check.run() == ''

        self.assertEqual(len(topology.get_snapshot(self.check.check_id)['components']), 0)
        self.assertEquals(len(topology.get_snapshot(self.check.check_id)['relations']), 0)

    def test_does_not_exceed_parallel_dispatches(self):
        saved_searches_parallel = 2

        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'saved_searches_parallel': saved_searches_parallel,
            'component_saved_searches': [
                {"name": "savedsearch1", "element_type": "component", "parameters": {}},
                {"name": "savedsearch2", "element_type": "component", "parameters": {}},
                {"name": "savedsearch3", "element_type": "component", "parameters": {}}
            ],
            'relation_saved_searches': [
                {"name": "savedsearch4", "element_type": "relation", "parameters": {}},
                {"name": "savedsearch5", "element_type": "relation", "parameters": {}}
            ]
        }

        self.check = MockedSplunkTopologyCheckParallel(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

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

        assert self.check._dispatch_parameters == {'dispatch.now': True, 'force_dispatch': True, 'output_mode': 'json'}

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

        assert self.check._dispatch_parameters == {'respect': 'me', 'output_mode': 'json'}

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

        assert self.check._dispatch_parameters == {'respect': 'me', 'output_mode': 'json'}

    def test_check_exception_continue(self):
        """
        When 1 saved search fails with Check Exception, the code should continue and send topology.
        """
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'ignore_saved_search_errors': True,
            'component_saved_searches': [
                {"name": "components", "search_max_retry_count": 0, "parameters": {}},
                {"name": "exception", "search_max_retry_count": 0, "parameters": {}}
            ],
            'relation_saved_searches': []
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

        self.assertEqual(len(topology.get_snapshot(self.check.check_id)['components']), 2)
        self.assertEquals(len(topology.get_snapshot(self.check.check_id)['relations']), 0)

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 1)

    def test_check_exception_false_no_continue(self):
        """
        When 1 saved search fails with Check Exception, the code should break and clear the whole topology.
        """
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'ignore_saved_search_errors': False,
            'component_saved_searches': [
                {"name": "components", "search_max_retry_count": 0, "parameters": {}},
                {"name": "exception", "search_max_retry_count": 0, "parameters": {}}
            ],
            'relation_saved_searches': []
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() != ''

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)

    def test_check_exception_fail_count_continue(self):
        """
        When both saved search fails with Check Exception, the code should continue and send topology.
        """
        instance = {
            'url': 'http://localhost:8089',
            'authentication': {
                'basic_auth': {
                    'username': "admin",
                    'password': "admin"
                }
            },
            'ignore_saved_search_errors': True,
            'component_saved_searches': [
                {"name": "incomplete_components", "search_max_retry_count": 0, "parameters": {}},
                {"name": "exception", "search_max_retry_count": 0, "parameters": {}}
            ],
            'relation_saved_searches': []
        }

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

        topology.assert_snapshot(self.check.check_id, self.instance_key, True, True, [], [])

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 1)
        self.assertEqual(service_checks[0].message,
                         "All result of saved search 'incomplete_components' contained incomplete data")
        self.assertEqual(service_checks[1].status, 1)
        self.assertEqual(service_checks[1].message, "maximum retries reached for saved search exception")

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

        self.check = MockedSplunkTopologyInvalidToken(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() == ''

        msg = "Current in use authentication token is expired. Please provide a valid token in the YAML and restart " \
              "the Agent"

        service_checks = aggregator.service_checks(SplunkTopology.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, msg)

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

        self.check = MockedSplunkTopologyInvalidToken(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() != ''

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

        self.check = MockedSplunkTopology(self.CHECK_NAME, {}, {}, [instance])
        assert self.check.run() != ''
