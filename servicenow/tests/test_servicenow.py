# -*- coding: utf-8 -*-

# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from copy import copy

import mock
import json
import unittest
import pytest
from yaml.parser import ParserError

from stackstate_checks.base.errors import CheckException
from stackstate_checks.servicenow import ServicenowCheck, InstanceInfo
from stackstate_checks.base.stubs import topology, aggregator
from stackstate_checks.base import AgentIntegrationTestUtil, AgentCheck, ConfigurationError


def mock_process_and_cache_relation_types(*args):
    return


def mock_collect_process(*args):
    return


# Mock behaviour(response) from ServiceNow API for Components(CIs)
mock_collect_components = {
    'result': [
        {
            'sys_class_name': 'cmdb_ci_computer',
            'sys_id': '00a96c0d3790200044e0bfc8bcbe5db4',
            'sys_created_on': '2012-02-18 08:14:21',
            'name': 'MacBook Pro 15'
        }
    ]
}

mock_collect_components_batch = {
    'result': [
        {
            'sys_class_name': 'cmdb_ci_computer',
            'sys_id': '00a96c0d3790200044e0bfc8bcbe5db4',
            'sys_created_on': '2012-02-18 08:14:21',
            'name': 'MacBook Pro 15'
        },
        {
            "sys_class_name": "cmdb_ci_computer",
            "sys_id": "00a9a80d3790200044e0bfc8bcbe5d1c",
            "sys_created_on": "2012-02-18 08:13:32",
            "name": "MacBook Air 13\""
        },
        {
            "sys_class_name": "cmdb_ci_computer",
            "sys_id": "00a9e80d3790200044e0bfc8bcbe5d42",
            "sys_created_on": "2012-02-18 08:13:48",
            "name": "MacBook Pro 17\""
        },
        {
            "sys_class_name": "cmdb_ci_computer",
            "sys_id": "01a9e40d3790200044e0bfc8bcbe5dab",
            "sys_created_on": "2012-02-18 08:12:30",
            "name": "ThinkStation C20"
        },
        {
            "sys_class_name": "cmdb_ci_computer",
            "sys_id": "01a9ec0d3790200044e0bfc8bcbe5dc3",
            "sys_created_on": "2012-02-18 08:14:42",
            "name": "ThinkStation C20"
        }
    ]
}

mock_collect_filter_components = {
    'result': [
        {
            'sys_class_name': 'cmdb_ci_cluster',
            'sys_id': '00a96c0d3790200044e0bfc8bcbe5db4',
            'sys_created_on': '2012-02-18 18:14:21',
            'name': 'Test Cluster'
        }
    ]
}

# Mock behaviour for relation types
mock_relation_types = {
    'result': [
        {
            'parent_descriptor': 'Cools',
            'sys_id': '53979c53c0a801640116ad2044643fb2'
        }
    ]
}

# Mock response from ServiceNow API for relation between components
mock_relation_components = {
    'result': [
        {
            'type': {
                'link': 'https://dev60476.service-now.com/api/now/table/cmdb_rel_type/1a9cb166f1571100a92eb60da2bc',
                'value': '1a9cb166f1571100a92eb60da2bce5c5'
            },
            'parent': {
                'link': 'https://dev60476.service-now.com/api/now/table/cmdb_ci/451047c6c0a8016400de0ae6df9b9d76',
                'value': '451047c6c0a8016400de0ae6df9b9d76'},
            'child': {
                'link': 'https://dev60476.service-now.com/api/now/table/cmdb_ci/53979c53c0a801640116ad2044643fb2',
                'value': '53979c53c0a801640116ad2044643fb2'
            }
        }
    ]
}

# Mock response from ServiceNow API for relation between components
mock_relation_with_filter = {
    'result': [
        {'type': {
            'link': 'https://dev60476.service-now.com/api/now/table/cmdb_rel_type/1a9cb166f1571100a92eb60da2bce5c5',
            'value': '1a9cb166f1571100a92eb60da2bce5c5'},
            'parent': {
                'link': 'https://dev60476.service-now.com/api/now/table/cmdb_ci/451047c6c0a8016400de0ae6df9b9d76',
                'value': '451047c6c0a8016400de0ae6df9b9d76'},
            'child': {
                'link': 'https://dev60476.service-now.com/api/now/table/cmdb_ci/53979c53c0a801640116ad2044643fb2',
                'value': '53979c53c0a801640116ad2044643fb2'
            }}
    ]
}

mock_empty_result = {'result': []}

mock_result_with_utf8 = {
    "result": {
        "name": u"Avery® Wizard 2.1 forMicrosoft® Word 2000",
        "sys_class_name": "cmdb_ci_spkg",
        "sys_id": "46b9874fa9fe1981017a4a80aaa07919"
    }
}

mock_result_malformed_str_with_error_msg = '''
{
  "result": [
    {
      "asset": {
        "name": "apc3276",
        "sys_id": "375924dfdb6fb2882f74f12aaf9619b8",
        "sys_created_on": "2017-06-29 11:03:27",
        "sys_class_name": "cmdb_ci_linux_server"
      },
    }""
  ],
  "error": {
    "detail": "Transaction cancelled: maximum execution time exceeded. Check logs for error trace.",
    "message": "Transaction cancelled: maximum execution time exceeded"
  },
  "status": "failure"
}
'''

mock_result_with_malformed_str = '''
{
  "result": [
    {
      "asset": {
        "name": "apc3276",
        "sys_id": "375924dfdb6fb2882f74f12aaf9619b8",
        "sys_created_on": "2017-06-29 11:03:27",
        "sys_class_name": "cmdb_ci_linux_server"
      },
    }""
  ]
}
'''

mock_instance = {
    'url': "https://dev60476.service-now.com",
    'user': 'name',
    'password': 'secret'
}

instance_config = InstanceInfo(
    instance_tags=[],
    base_url=mock_instance.get('url'),
    auth=(mock_instance.get('user'), mock_instance.get('password')),
    sys_class_filter=[],
    batch_size=100,
    timeout=10
)


def mock_get_json(url, timeout, auth=None, verify=True):
    """Mock method for testing _get_json_batch"""
    return url


@pytest.mark.usefixtures("instance")
class TestServicenow(unittest.TestCase):
    """Basic Test for servicenow integration."""

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        self.check = ServicenowCheck('servicenow_test', config={}, instances=[self.instance])
        topology.reset()
        aggregator.reset()

    def test_check(self):
        """
        Testing Servicenow check.
        """
        self.check._process_relation_types = mock_process_and_cache_relation_types
        self.check._collect_and_process = mock_collect_process

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 0)

        AgentIntegrationTestUtil.assert_integration_snapshot(self.check,
                                                             'servicenow_cmdb:https://dev60476.service-now.com')

    def test_when_check_has_exception_stop_snapshot_is_false(self):
        """
        Test to raise a check exception when collecting components
        """
        self.check._get_json = mock.MagicMock()
        self.check._get_json.side_effect = Exception("Test exception occurred")
        self.assertRaises(Exception, self.check.check(mock_instance))

        # since the check raised exception, the topology snapshot is not completed
        topo_instance = topology.get_snapshot(self.check.check_id)
        self.assertEqual(topo_instance.get("start_snapshot"), True)
        self.assertEqual(topo_instance.get("stop_snapshot"), False)

        # Service Checks should be generated
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_NAME)
        self.assertEqual(len(service_checks), 1)
        self.assertEqual(service_checks[0].name, self.check.SERVICE_CHECK_NAME)
        self.assertEqual(service_checks[0].status, AgentCheck.CRITICAL)

    def test_process_components(self):
        """
        Test _process_components to return topology for components
        """
        self.check._collect_components = mock.MagicMock()
        self.check._collect_components.return_value = mock_collect_components
        self.check._collect_and_process(self.check._collect_components, self.check._process_components, instance_config)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 1)
        self.assertEqual(len(topo_instances['relations']), 0)
        self.assertEqual(topo_instances['components'][0]['type'], 'cmdb_ci_computer')
        self.assertEqual(topo_instances['components'][0]['data']['identifiers'],
                         ["urn:host:/MacBook Pro 15", "00a96c0d3790200044e0bfc8bcbe5db4"])

    def test_collect_relation_types(self):
        """
        Test to raise a check exception when collecting relation types
        """
        self.assertRaises(Exception, self.check._collect_relation_types, instance_config)

    def test_process_relation_types(self):
        """
        Test to collect relation types from ServiceNow API and put in relation_types
        """
        self.check._collect_relation_types = mock.MagicMock()
        self.check._collect_relation_types.return_value = mock_relation_types
        out = self.check._process_relation_types(instance_config)

        self.assertEqual(len(out), 1)

    def test_collect_relations(self):
        """
        Test to raise a check Exception while collecting component relations from ServiceNow API
        """
        self.assertRaises(Exception, self.check._collect_relations, instance_config, 10, 0, 100)

    def test_process_relations(self):
        """
        Test to collect the component relations and process it as a topology
        """
        self.check._process_relation_types = mock.MagicMock()
        self.check._process_relation_types.return_value = {'1a9cb166f1571100a92eb60da2bce5c5': 'Cools'}
        self.check._collect_relations = mock.MagicMock()
        self.check._collect_relations.return_value = mock_relation_components
        self.check._collect_and_process(self.check._collect_relations, self.check._process_relations, instance_config)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(topo_instances['relations'][0]['type'], 'Cools')

    @mock.patch('requests.get')
    def test_get_json_ok_status(self, mock_req_get):
        """
        Test to check the method _get_json with positive response and get a OK service check
        """
        url, auth = self._get_url_auth()
        example = {'key': 'value'}
        mock_req_get.return_value = mock.MagicMock(status_code=200, text=json.dumps(example))
        result = self.check._get_json(url, timeout=10, auth=auth)
        self.assertEqual(example, result)

    @mock.patch('requests.get')
    def test_get_json_error_status(self, mock_req_get):
        """
        Test for Check Exception if response code is not 200
        """
        url, auth = self._get_url_auth()
        mock_req_get.return_value = mock.MagicMock(status_code=300, text=json.dumps({'key': 'value'}))
        self.assertRaises(CheckException, self.check._get_json, url, 10, auth)

    @mock.patch('requests.get')
    def test_get_json_ok_status_with_error_in_response(self, mock_req_get):
        """
        Test for situation when we get error in json and request status is OK
        """
        url, auth = self._get_url_auth()
        response_txt = json.dumps({'error': {'message': 'test error'}})
        mock_req_get.return_value = mock.MagicMock(status_code=200, text=response_txt)
        self.assertRaises(CheckException, self.check._get_json, url, 10, auth)

    def test_get_sys_class_component_filter_query(self):
        """
        Test to check if the method creates the proper param query
        """
        sys_class_filter = self.instance.get('include_resource_types')
        self.assertEqual(len(sys_class_filter), 3)
        query = self.check.get_sys_class_component_filter_query(sys_class_filter)
        expected_query = "sysparm_query=sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server"
        self.assertEqual(query, expected_query)

    def test_get_sys_class_relation_filter_query(self):
        """
        Test to check if the method creates the proper param query
        """
        sys_class_filter = self.instance.get('include_resource_types')
        self.assertEqual(len(sys_class_filter), 3)
        query = self.check.get_sys_class_relation_filter_query(sys_class_filter)
        expected_query = "sysparm_query=parent.sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server" \
                         "%5Echild.sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server"
        self.assertEqual(query, expected_query)

    def test_process_components_with_sys_filter_change(self):
        """
        Test _process_components to return whole topology when query changed in between
        """
        sys_class_filter = self.instance.get('include_resource_types')
        instance_config.sys_class_filter = sys_class_filter
        query_filter = self.check.get_sys_class_component_filter_query(sys_class_filter)
        expected_query = "sysparm_query=sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server"
        # asserting the actual query
        self.assertEqual(query_filter, expected_query)

        self.check.get_sys_class_component_filter_query = mock.MagicMock()
        # changing the query in between and returning with incorrect query
        self.check.get_sys_class_component_filter_query.return_value = "sysparm_query=sys_class_namecmdb_ci_netgear" \
                                                                       "%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server"
        self.check._get_json = mock.MagicMock()
        self.check._get_json.return_value = mock_collect_components
        self.check._collect_and_process(self.check._collect_components, self.check._process_components, instance_config)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 1)
        self.assertEqual(len(topo_instances['relations']), 0)
        self.assertEqual(topo_instances['components'][0]['type'], 'cmdb_ci_computer')

    def test_process_component_relations_with_sys_filter_change(self):
        """
        Test _process_components to return whole topology when query changed in between
        """
        sys_class_filter = self.instance.get('include_resource_types')
        instance_config.sys_class_filter = sys_class_filter
        query_filter = self.check.get_sys_class_relation_filter_query(sys_class_filter)
        expected_query = "sysparm_query=parent.sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server" \
                         "%5Echild.sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server"
        # asserting the actual query
        self.assertEqual(query_filter, expected_query)

        self.check.get_sys_class_relation_filter_query = mock.MagicMock()
        # changing the query in between and returning with incorrect query
        self.check.get_sys_class_relation_filter_query.return_value = "sysparm_query=parent.sys_class_nameN" \
                                                                      "cmdb_ci_netgear%5Echild.sys_class_nameIN" \
                                                                      "cmdb_ci_netgear"
        self.check._get_json = mock.MagicMock()
        self.check._get_json.return_value = mock_relation_components
        self.check._process_relation_types = mock.MagicMock()
        self.check._process_relation_types.return_value = {'1a9cb166f1571100a92eb60da2bce5c5': 'Cools'}
        self.check._collect_and_process(self.check._collect_relations, self.check._process_relations, instance_config)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 1)
        self.assertEqual(topo_instances['relations'][0]['type'], 'Cools')

    def test_process_components_without_sys_filter_change(self):
        """
        Test _process_components to return whole topology when query changed in between
        """
        sys_class_filter = self.instance.get('include_resource_types')
        instance_config.sys_class_filter = sys_class_filter
        query_filter = self.check.get_sys_class_component_filter_query(sys_class_filter)
        expected_query = "sysparm_query=sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server"
        # asserting the actual query
        self.assertEqual(query_filter, expected_query)

        self.check._get_json = mock.MagicMock()
        self.check._get_json.return_value = mock_collect_filter_components
        self.check._collect_and_process(self.check._collect_components, self.check._process_components, instance_config)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 1)
        self.assertEqual(len(topo_instances['relations']), 0)
        # Since the filter gets specific component types only so returned one component
        self.assertEqual(topo_instances['components'][0]['type'], 'cmdb_ci_cluster')

    def test_process_relations_without_sys_filter_change(self):
        """
        Test _process_components to return whole topology when query changed in between
        """
        sys_class_filter = self.instance.get('include_resource_types')
        instance_config.sys_class_filter = sys_class_filter
        query_filter = self.check.get_sys_class_relation_filter_query(sys_class_filter)
        expected_query = "sysparm_query=parent.sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server" \
                         "%5Echild.sys_class_nameINcmdb_ci_netgear%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server"
        # asserting the actual query
        self.assertEqual(query_filter, expected_query)

        self.check._get_json = mock.MagicMock()
        self.check._get_json.return_value = mock_relation_with_filter
        self.check._process_relation_types = mock.MagicMock()
        self.check._process_relation_types.return_value = {'1a9cb166f1571100a92eb60da2bce5c5': 'Cools'}

        self.check._collect_and_process(self.check._collect_relations, self.check._process_relations, instance_config)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        # Since the filter gets specific relation only so returned one relation for filtered resource types
        self.assertEqual(len(topo_instances['relations']), 1)
        self.assertEqual(topo_instances['relations'][0]['type'], 'Cools')

    def test_batch_collect(self):
        """
        Test batch collecting components
        """
        self.check._collect_components = mock.MagicMock()
        self.check._collect_components.side_effect = [mock_collect_components_batch, mock_collect_components]
        new_inst_conf = copy(instance_config)
        new_inst_conf.batch_size = 5
        self.check._collect_and_process(self.check._collect_components, self.check._process_components, new_inst_conf)

        topology_instance = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topology_instance['components']), 6)

    def test_mandatory_instance_values(self):
        """
        Test existence of mandatory instance values
        """
        self.assertRaises(ConfigurationError, self.check.check, {'user': 'name', 'password': 'secret'})
        self.assertRaises(ConfigurationError, self.check.check, {'user': 'name', 'url': "https://website.com"})
        self.assertRaises(ConfigurationError, self.check.check, {'password': 'secret', 'url': "https://website.com"})
        self.assertRaises(ConfigurationError, self.check.get_instance_key, {})

    def test_json_batch(self):
        """
        Test if batch path construction
        """
        self.check._get_json = mock_get_json
        url, auth = self._get_url_auth()
        offset = 10
        batch_size = 200
        expected_url = '{}?sysparm_query=ORDERBYsys_created_on&sysparm_offset={}&sysparm_limit={}'.format(url,
                                                                                                          offset,
                                                                                                          batch_size)
        new_url = self.check._get_json_batch(url=url, offset=10, batch_size=200, timeout=10, auth=auth)
        self.assertEqual(expected_url, new_url)

        url2 = '{}?k=v'.format(url)
        expected_url2 = '{}&sysparm_query=ORDERBYsys_created_on&sysparm_offset={}&sysparm_limit={}'.format(url2,
                                                                                                           offset,
                                                                                                           batch_size)
        new_url = self.check._get_json_batch(url=url2, offset=10, batch_size=200, timeout=10, auth=auth)
        self.assertEqual(expected_url2, new_url)

    def test_collect_components_returns_no_result(self):
        """Test if collect component returns no result or its not list"""
        self.check._collect_components = mock.MagicMock()
        self.check._collect_components.return_value = {}
        self.assertRaises(CheckException, self.check._collect_and_process,
                          self.check._collect_components, self.check._process_components, instance_config)

    def test_collect_components_returns_empty_result(self):
        """Test if collect component returns no result or its not list"""
        self.check._collect_components = mock.MagicMock()
        self.check._collect_components.return_value = mock_empty_result
        self.check._collect_and_process(self.check._collect_components, self.check._process_components, instance_config)

        # no snapshot is created
        self.assertRaises(KeyError, topology.get_snapshot, self.check.check_id)

    def test_batch_collect_exact_result_as_batch_size(self):
        """
        Test batch collecting components
        """
        self.check._collect_components = mock.MagicMock()
        self.check._collect_components.side_effect = [mock_collect_components_batch, mock_empty_result]
        new_inst_conf = copy(instance_config)
        new_inst_conf.batch_size = 5
        self.check._collect_and_process(self.check._collect_components, self.check._process_components, new_inst_conf)

        topology_instance = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topology_instance['components']), 5)

    @mock.patch('requests.get')
    def test_get_json_utf_encoding(self, mock_req_get):
        """
        Test to check the method _get_json response with unicode character in name
        """
        url, auth = self._get_url_auth()
        mock_req_get.return_value = mock.MagicMock(status_code=200, text=json.dumps(mock_result_with_utf8))
        response = self.check._get_json(url, timeout=10, auth=auth)
        self.assertEqual(u'Avery® Wizard 2.1 forMicrosoft® Word 2000', response.get('result').get('name'))

    @mock.patch('requests.get')
    def test_get_json_malformed_json(self, mock_request_get):
        """
        Test just malformed json
        """
        url, auth = self._get_url_auth()
        mock_request_get.return_value = mock.MagicMock(status_code=200, text=mock_result_with_malformed_str)
        self.assertRaises(ParserError, self.check._get_json, url, 10, auth)

    @mock.patch('requests.get')
    def test_get_json_malformed_json_and_execution_time_exceeded_error(self, mock_request_get):
        """
        Test malformed json that sometimes happens with
        ServiceNow error 'Transaction cancelled: maximum execution time exceeded'
        """
        url, auth = self._get_url_auth()
        mock_request_get.return_value = mock.MagicMock(status_code=200, text=mock_result_malformed_str_with_error_msg)
        self.assertRaises(CheckException, self.check._get_json, url, 10, auth)

    def test_batch_size(self):
        """
        Test max batch size value
        """
        instance = {'user': 'name', 'password': 'secret', 'url': "https://website.com", 'batch_size': 20000}
        self.assertRaises(ConfigurationError, self.check.check, instance)

    def _get_url_auth(self):
        url = "{}/api/now/table/cmdb_ci".format(self.instance.get('url'))
        auth = (self.instance.get('user'), self.instance.get('password'))
        return url, auth
