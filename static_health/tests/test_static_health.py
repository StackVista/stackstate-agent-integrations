# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# 3p
import mock
import unittest
import json

from stackstate_checks.base import AgentIntegrationTestUtil
from stackstate_checks.static_health import StaticHealthCheck
from stackstate_checks.base.stubs import health, topology


class MockFileReader:
    """used to mock codec.open, it returns content for a with-construct."""

    def __init__(self, location, content):
        """
        :param location: the csv file location, used to return value of content[location]
        :param content: dict(key: location, value: array of to delimit strings)
        """
        self.content = content
        self.location = location

    def __enter__(self):
        return self.content[self.location]

    def __exit__(self, type, value, traceback):
        pass


class TestStaticCSVHealth(unittest.TestCase):
    """
    Unit tests for Static Health AgentCheck.
    """
    CHECK_NAME = "static_health"

    instance = {
        'type': 'csv',
        'health_file': 'health.csv',
        'delimiter': ',',
        'collection_interval': 15
    }

    config = {
        'init_config': {},
        'instances': [instance]
    }

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        # Initialize
        config = {}
        self.check = StaticHealthCheck(self.CHECK_NAME, config, instances=[self.instance])
        # We clear these guys here. We'd like to use these as fixtures, but fixture do not play nice with unittest,
        # see https://stackoverflow.com/questions/22677654/why-cant-unittest-testcases-see-my-py-test-fixtures
        health.reset()
        topology.reset()

    def test_omitted_health_file(self):
        instance = {
            'type': 'csv',
            'delimiter': ';',
            'collection_interval': 15
        }

        config = {
            'init_config': {},
            'instances': [instance]
        }

        self.check = StaticHealthCheck(self.CHECK_NAME, config, instances=[instance])
        assert json.loads(self.check.run())[0]['message'] == '{"health_file": ["This field is required."]}'

    def test_empty_health_file(self):
        instance = {
            'type': 'csv',
            'health_file': '/dev/null',
            'delimiter': ';',
            'collection_interval': 15
        }

        config = {
            'init_config': {},
            'instances': [instance]
        }

        self.check = StaticHealthCheck(self.CHECK_NAME, config, instances=[instance])

        assert json.loads(self.check.run())[0]['message'] == 'Health CSV file is empty.'
        # Snapshot will be started but not stopped
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15})

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'health.csv': ['check_state_id,name,health,topology_element_identifier',
                                   '1,name1,clear,id1', '2,name2,critical,id2']}))
    def test_health_min_values(self, mock):
        assert self.check.run() == ""
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                               stop_snapshot={},
                               check_states=[{'checkStateId': '1',
                                              'health': 'CLEAR',
                                              'name': 'name1',
                                              'topologyElementIdentifier': 'id1'},
                                             {'checkStateId': '2',
                                              'health': 'CRITICAL',
                                              'name': 'name2',
                                              'topologyElementIdentifier': 'id2'},
                                             ])
        AgentIntegrationTestUtil.assert_integration_snapshot(self.check, 'StaticHealth:health.csv')

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'health.csv': ['check_state_id,name,health,topology_element_identifier,message',
                                   '1,name1,clear,id1,message', '2,name2,critical,id2,']}))
    def test_health_max_values(self, mock):
        assert self.check.run() == ""
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                               stop_snapshot={},
                               check_states=[{'checkStateId': '1',
                                              'health': 'CLEAR',
                                              'name': 'name1',
                                              'message': 'message',
                                              'topologyElementIdentifier': 'id1'},
                                             {'checkStateId': '2',
                                              'health': 'CRITICAL',
                                              'name': 'name2',
                                              'topologyElementIdentifier': 'id2'},
                                             ])
        AgentIntegrationTestUtil.assert_integration_snapshot(self.check, 'StaticHealth:health.csv')

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
                'health.csv': ['no_check_state_id,name,health,topology_element_identifier']}))
    def test_missing_check_id_field(self, mock):
        assert json.loads(self.check.run())[0]['message'] == 'CSV header check_state_id not found in health csv.'
        # Snapshot will be started but not stopped
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15})

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
                'health.csv': ['check_state_id,no_name,health,topology_element_identifier']}))
    def test_missing_name_field(self, mock):
        assert json.loads(self.check.run())[0]['message'] == 'CSV header name not found in health csv.'
        # Snapshot will be started but not stopped
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15})

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
                'health.csv': ['check_state_id,name,no_health,topology_element_identifier']}))
    def test_missing_health_field(self, mock):
        assert json.loads(self.check.run())[0]['message'] == 'CSV header health not found in health csv.'
        # Snapshot will be started but not stopped
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15})

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
                'health.csv': ['check_state_id,name,health,no_topology_element_identifier']}))
    def test_missing_topology_element_identifier_field(self, mock):
        assert json.loads(self.check.run())[0]['message'] ==\
               'CSV header topology_element_identifier not found in health csv.'
        # Snapshot will be started but not stopped
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15})

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
                'health.csv': ['check_state_id,name,health,topology_element_identifier', '1,name,blaat,id1']}))
    def test_wrong_health(self, mock):
        assert json.loads(self.check.run())[0]['message'] == '["Health value must be clear, deviating or critical"]'
        # Snapshot will be started but not stopped
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15})

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
                'health.csv': ['check_state_id,name,health,topology_element_identifier', '1,name1,clear,id1', '']}))
    def test_handle_empty_line(self, mock):
        assert self.check.run() == ""
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                               stop_snapshot={},
                               check_states=[{'checkStateId': '1',
                                              'health': 'CLEAR',
                                              'name': 'name1',
                                              'topologyElementIdentifier': 'id1'}
                                             ])

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
                'health.csv': ['check_state_id,name,health,topology_element_identifier',
                               '1,name1,clear,id1,message', '2,name2,critical']}))
    def test_handle_incomplete_line(self, mock):
        assert self.check.run() == ""
        health.assert_snapshot(self.check.check_id, self.check.health.stream,
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                               stop_snapshot={},
                               check_states=[{'checkStateId': '1',
                                              'health': 'CLEAR',
                                              'name': 'name1',
                                              'topologyElementIdentifier': 'id1'}
                                             ])
