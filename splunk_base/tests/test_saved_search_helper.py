# stdlib
import unittest
import logging

# project
from stackstate_checks.splunk.config import SplunkInstanceConfig, SplunkSavedSearch, SplunkPersistentState
from stackstate_checks.splunk.client import FinalizeException
from test_splunk_instance_config import mock_defaults
from stackstate_checks.splunk.saved_search_helper import SavedSearches
from stackstate_checks.base import AgentCheck
from stackstate_checks.base.errors import CheckException


class MockSplunkClient(object):
    def __init__(self):
        self.saved_searches_result = []
        self.saved_search_results_results = {}
        self.dispatch_results = {}
        self.finalized = []
        self.max_parallel_searches = 999
        self.parallel_searches = 0

    def saved_searches(self):
        return self.saved_searches_result

    def saved_search_results(self, search_id, saved_search):
        self.parallel_searches -= 1
        return self.saved_search_results_results[search_id]

    def dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        self.parallel_searches += 1
        assert self.parallel_searches <= self.max_parallel_searches
        return self.dispatch_results[saved_search.name]

    def finalize_sid(self, search_id, saved_search):
        self.finalized.append(search_id)
        return


class MockSplunkClientFailFinalize(MockSplunkClient):
    def __init__(self, *args, **kwargs):
        super(MockSplunkClientFailFinalize, self).__init__(*args, **kwargs)

    def finalize_sid(self, search_id, saved_search):
        self.finalized.append(search_id)
        raise FinalizeException(0, "Broken")


base_instance = {
    'url': 'http://localhost:8089',
    'authentication': {
        'basic_auth': {
            'username': "adminNew",
            'password': "adminNew"
        }
    },
    'tags': ['mytag', 'mytag2']
}


class MockServiceCheck(object):
    def __init__(self):
        self.results = []
        self.ret_val = 0

        def _service_check(status, tags=None, hostname=None, message=None):
            self.results.append([status, tags, hostname, message])

        self.function = _service_check


class MockProcessData(object):
    def __init__(self):
        self.results = []
        self.ret_val = 0

        def _process_data(saved_search, response, sent_already):
            self.results.append(response)
            return self.ret_val

        self.function = _process_data


class TestSplunkInstanceConfig(unittest.TestCase):

    def setUp(self):
        self.log = logging.getLogger('%s' % __name__)
        self.committable_state = SplunkPersistentState({})
        self.mock_service_check = MockServiceCheck()
        self.mock_process_data = MockProcessData()
        self.mock_splunk_client = MockSplunkClient()

    def test_no_saved_searches(self):
        searches = SavedSearches(SplunkInstanceConfig(base_instance, {}, mock_defaults), self.mock_splunk_client, [])
        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert self.mock_process_data.results == []
        assert self.mock_service_check.results == [[AgentCheck.OK, None, None, None]]

    def test_process_data_no_app(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client, [SplunkSavedSearch(instance, {'name': 'search1'}),
                                                                     SplunkSavedSearch(instance, {'name': 'search2'})])
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'
        self.mock_splunk_client.dispatch_results['search2'] = 'sid2'

        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        data2 = {'messages': [], 'results': [{'data': 'result2'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]
        self.mock_splunk_client.saved_search_results_results['sid2'] = [data2]

        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert self.mock_process_data.results == [data1, data2]
        assert self.mock_service_check.results == [[AgentCheck.OK, None, None, None]]

    def test_process_data_with_app(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client,
                                 [SplunkSavedSearch(instance, {'name': 'search1', 'app': 'myapp1'}),
                                  SplunkSavedSearch(instance, {'name': 'search2', 'app': 'myapp2'})])
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'
        self.mock_splunk_client.dispatch_results['search2'] = 'sid2'

        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        data2 = {'messages': [], 'results': [{'data': 'result2'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]
        self.mock_splunk_client.saved_search_results_results['sid2'] = [data2]

        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert self.mock_process_data.results == [data1, data2]
        assert self.mock_service_check.results == [[AgentCheck.OK, None, None, None]]

    def test_process_data_with_and_without_app(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client,
                                 [SplunkSavedSearch(instance, {'name': 'search1', 'app': 'myapp1'}),
                                  SplunkSavedSearch(instance, {'name': 'search2'})])
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'
        self.mock_splunk_client.dispatch_results['search2'] = 'sid2'

        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        data2 = {'messages': [], 'results': [{'data': 'result2'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]
        self.mock_splunk_client.saved_search_results_results['sid2'] = [data2]

        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert self.mock_process_data.results == [data1, data2]
        assert self.mock_service_check.results == [[AgentCheck.OK, None, None, None]]

    def test_store_and_finalize_sids(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client, [SplunkSavedSearch(instance, {'name': 'breaking'})])

        # Dispatch should succeed, but not the result retrieval
        self.mock_splunk_client.dispatch_results['breaking'] = 'sid1'

        issue = True
        try:
            searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                        self.committable_state)
            issue = False
        except Exception:
            issue = True
        assert issue
        assert self.mock_service_check.results == [[AgentCheck.WARNING, ['mytag', 'mytag2'], None, "'sid1'"]]
        assert self.committable_state.state == {'sid_breaking': 'sid1'}

        # Make sure it now runs correctly
        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]

        # Run again, this finalizes and reruns the search
        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert self.mock_splunk_client.finalized == ['sid1']
        assert len(self.mock_service_check.results) == 2
        assert [AgentCheck.OK, None, None, None] in self.mock_service_check.results
        assert [AgentCheck.WARNING, ['mytag', 'mytag2'], None, "'sid1'"] in self.mock_service_check.results
        assert self.committable_state.state == {'sid_breaking': 'sid1'}

    def test_keep_sid_when_finalize_fails(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        mock_splunk_client = MockSplunkClientFailFinalize()
        searches = SavedSearches(instance, mock_splunk_client, [SplunkSavedSearch(instance, {'name': 'breaking'})])

        # Dispatch should succeed, but not the result retrieval
        mock_splunk_client.dispatch_results['breaking'] = 'sid1'

        issue = None
        try:
            searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                        self.committable_state)
            issue = False
        except Exception:
            issue = True
        assert issue
        assert self.mock_service_check.results == [[AgentCheck.WARNING, ['mytag', 'mytag2'], None, "'sid1'"]]
        assert self.committable_state.state == {'sid_breaking': 'sid1'}

        # Run again, this will trigger an issue during finalize
        issue2 = None
        try:
            searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                        self.committable_state)
            issue2 = False
        except FinalizeException:
            issue2 = True
        assert issue2

        assert mock_splunk_client.finalized == ['sid1']
        assert self.mock_service_check.results == [[AgentCheck.WARNING, ['mytag', 'mytag2'], None, "'sid1'"]]
        assert self.committable_state.state == {'sid_breaking': 'sid1'}

    def test_incomplete_data(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client, [SplunkSavedSearch(instance, {'name': 'search1'}),
                                                                     SplunkSavedSearch(instance, {'name': 'search2'})])
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'
        self.mock_splunk_client.dispatch_results['search2'] = 'sid2'

        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        data2 = {'messages': [], 'results': [{'data': 'result2'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]
        self.mock_splunk_client.saved_search_results_results['sid2'] = [data2]
        self.mock_process_data.ret_val = 1

        issue = None
        try:
            searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                        self.committable_state)
            issue = False
        except CheckException:
            issue = True
        assert issue

        assert self.mock_process_data.results == [data1]
        assert self.mock_service_check.results == [[AgentCheck.WARNING, ['mytag', 'mytag2'], None,
                                                    "All result of saved search 'search1' contained incomplete data"]]

    def test_partially_incomplete_data(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client, [SplunkSavedSearch(instance, {'name': 'search1'})])
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'
        self.mock_splunk_client.dispatch_results['search2'] = 'sid2'

        data1 = {'messages': [], 'results': [{'data': 'result1'}, {'data': 'result2'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]
        self.mock_process_data.ret_val = 1

        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)

        assert self.mock_process_data.results == [data1]
        assert self.mock_service_check.results == [[AgentCheck.WARNING, ['mytag', 'mytag2'], None,
                                                    "The saved search 'search1' contained 1 incomplete records"]]

    def test_partially_incomplete_and_incomplete(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client, [SplunkSavedSearch(instance, {'name': 'search1'}),
                                                                     SplunkSavedSearch(instance, {'name': 'search2'})])
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'
        self.mock_splunk_client.dispatch_results['search2'] = 'sid2'

        data1 = {'messages': [], 'results': [{'data': 'result1'}, {'data': 'result1_2'}]}
        data2 = {'messages': [], 'results': [{'data': 'result2'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]
        self.mock_splunk_client.saved_search_results_results['sid2'] = [data2]
        self.mock_process_data.ret_val = 1

        issue = None
        try:
            searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                        self.committable_state)
            issue = False
        except CheckException:
            issue = True
        assert issue

        assert self.mock_process_data.results == [data1, data2]
        assert self.mock_service_check.results == [[AgentCheck.WARNING,
                                                    ['mytag', 'mytag2'],
                                                    None,
                                                    "The saved search 'search1' contained 1 incomplete records"],
                                                   [AgentCheck.WARNING,
                                                    ['mytag', 'mytag2'],
                                                    None,
                                                    "All result of saved search 'search2' contained incomplete data"]
                                                   ]

    def test_wildcard_topology(self):
        instance = SplunkInstanceConfig(base_instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client, [SplunkSavedSearch(instance, {'match': 'comp.*'}),
                                                                     SplunkSavedSearch(instance, {'match': 'rel.*'})])
        self.mock_splunk_client.saved_searches_result = ["components", "relations"]
        self.mock_splunk_client.dispatch_results['components'] = 'sid1'
        self.mock_splunk_client.dispatch_results['relations'] = 'sid2'

        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        data2 = {'messages': [], 'results': [{'data': 'result2'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]
        self.mock_splunk_client.saved_search_results_results['sid2'] = [data2]

        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert len(self.mock_process_data.results) == 2
        assert self.mock_service_check.results == [[AgentCheck.OK, None, None, None]]

        # Now drop all saved searches and see them disappear
        self.mock_splunk_client.saved_searches_result = []
        self.mock_process_data = MockProcessData()
        self.mock_service_check = MockServiceCheck()
        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert self.mock_process_data.results == []
        assert self.mock_service_check.results == [[AgentCheck.OK, None, None, None]]

    def test_does_not_exceed_parallel_dispatches(self):
        saved_searches_parallel = 2

        instance = {
            'url': 'http://localhost:8089',
            'saved_searches_parallel': saved_searches_parallel,
            'authentication': {
                'basic_auth': {
                    'username': "adminNew",
                    'password': "adminNew"
                }
            },
            'tags': ['mytag', 'mytag2']
        }

        instance = SplunkInstanceConfig(instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client, [SplunkSavedSearch(instance, {'name': 'search1'}),
                                                                     SplunkSavedSearch(instance, {'name': 'search2'}),
                                                                     SplunkSavedSearch(instance, {'name': 'search3'}),
                                                                     SplunkSavedSearch(instance, {'name': 'search4'})
                                                                     ])
        self.mock_splunk_client.max_parallel_searches = saved_searches_parallel

        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'
        self.mock_splunk_client.dispatch_results['search2'] = 'sid2'
        self.mock_splunk_client.dispatch_results['search3'] = 'sid3'
        self.mock_splunk_client.dispatch_results['search4'] = 'sid4'

        self.mock_splunk_client.saved_search_results_results['sid1'] = []
        self.mock_splunk_client.saved_search_results_results['sid2'] = []
        self.mock_splunk_client.saved_search_results_results['sid3'] = []
        self.mock_splunk_client.saved_search_results_results['sid4'] = []

        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert self.mock_process_data.results == []
        assert self.mock_service_check.results == [[AgentCheck.OK, None, None, None]]

    def test_ignore_saved_search_errors_continue(self):
        """
        When 1 saved search fails with Check Exception, the code should continue and send
        topology if issues are ignored.
        """
        instance = {
            'url': 'http://localhost:8089',
            'ignore_saved_search_errors': True,
            'authentication': {
                'basic_auth': {
                    'username': "adminNew",
                    'password': "adminNew"
                }
            },
            'tags': ['mytag', 'mytag2']
        }

        instance = SplunkInstanceConfig(instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client,
                                 [SplunkSavedSearch(instance, {'name': 'search_broken'}),
                                  SplunkSavedSearch(instance, {'name': 'search1'})])
        self.mock_splunk_client.dispatch_results['search_broken'] = 'sid_broken'
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'

        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]

        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)
        assert self.mock_process_data.results == [data1]
        assert self.mock_service_check.results == [[AgentCheck.WARNING, ['mytag', 'mytag2'], None, "'sid_broken'"]]

    def test_no_ignore_saved_search_errors_breaks(self):
        """
        When 1 saved search fails with Check Exception, the code
        should continue and send topology if issues are ignored.
        """
        instance = {
            'url': 'http://localhost:8089',
            'ignore_saved_search_errors': False,
            'authentication': {
                'basic_auth': {
                    'username': "adminNew",
                    'password': "adminNew"
                }
            },
            'tags': ['mytag', 'mytag2']
        }

        instance = SplunkInstanceConfig(instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client,
                                 [SplunkSavedSearch(instance, {'name': 'search_broken'}),
                                  SplunkSavedSearch(instance, {'name': 'search1'})])
        self.mock_splunk_client.dispatch_results['search_broken'] = 'sid_broken'
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'

        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]

        issue = True
        try:
            searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                        self.committable_state)
            issue = False
        except Exception:
            issue = True
        assert issue
        assert self.mock_process_data.results == []
        assert self.mock_service_check.results == [[AgentCheck.WARNING, ['mytag', 'mytag2'], None, "'sid_broken'"]]

    def test_incomplete_and_failing_produce_warnings(self):
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
        }

        instance = SplunkInstanceConfig(instance, {}, mock_defaults)
        searches = SavedSearches(instance, self.mock_splunk_client, [SplunkSavedSearch(instance, {'name': 'search1'}),
                                                                     SplunkSavedSearch(instance,
                                                                                       {'name': 'search_broken'})])
        self.mock_splunk_client.dispatch_results['search1'] = 'sid1'
        self.mock_splunk_client.dispatch_results['search_broken'] = 'broken_sid'

        data1 = {'messages': [], 'results': [{'data': 'result1'}]}
        self.mock_splunk_client.saved_search_results_results['sid1'] = [data1]
        self.mock_process_data.ret_val = 1

        searches.run_saved_searches(self.mock_process_data.function, self.mock_service_check.function, self.log,
                                    self.committable_state)

        assert self.mock_service_check.results == [[AgentCheck.WARNING, [], None,
                                                    "All result of saved search 'search1' contained incomplete data"],
                                                   [AgentCheck.WARNING, [], None, "'broken_sid'"]]
