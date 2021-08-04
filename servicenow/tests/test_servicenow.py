# -*- coding: utf-8 -*-

# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import json
import os
import unittest
from copy import copy

import mock
import pytest
import requests
from six import PY3

from stackstate_checks.base import AgentIntegrationTestUtil, AgentCheck, TopologyInstance
from stackstate_checks.base.errors import CheckException
from stackstate_checks.base.stubs import topology, aggregator, telemetry
from stackstate_checks.servicenow import ServiceNowCheck, InstanceInfo, State


def mock_collect_process(*args):
    return {'result': []}


# Mock behaviour(response) from ServiceNow API for Components(CIs)
mock_collect_components = {
    'result': [
        {
            'sys_class_name': {
                'display_value': 'Computer',
                'value': 'cmdb_ci_computer'
            },
            'sys_id': {
                'display_value': '00a96c0d3790200044e0bfc8bcbe5db4',
                'value': '00a96c0d3790200044e0bfc8bcbe5db4'
            },
            'sys_created_on': {
                'display_value': '2012-02-18 12:14:21',
                'value': '2012-02-18 08:14:21'
            },
            'sys_tags': {
                'display_value': 'stackstate-identifier:lupulus, stackstate',
                'value': ''
            },
            'name': {
                'display_value': 'MacBook Pro 15',
                'value': 'MacBook Pro 15'
            }
        }
    ]
}

mock_collect_components_batch = {
    'result': [
        {
            'sys_class_name': {
                'display_value': 'Computer',
                'value': 'cmdb_ci_computer'
            },
            'sys_id': {
                'display_value': '00a96c0d3790200044e0bfc8bcbe5db4',
                'value': '00a96c0d3790200044e0bfc8bcbe5db4'
            },
            'sys_created_on': {
                'display_value': '2012-02-18 12:14:21',
                'value': '2012-02-18 08:14:21'
            },
            'name': {
                'display_value': 'MacBook Pro 15',
                'value': 'MacBook Pro 15'
            }
        },
        {
            'sys_class_name': {
                'display_value': 'Computer',
                'value': 'cmdb_ci_computer'
            },
            'sys_id': {
                'display_value': '00a9a80d3790200044e0bfc8bcbe5d1c',
                'value': '00a9a80d3790200044e0bfc8bcbe5d1c'
            },
            'sys_created_on': {
                'display_value': '2012-02-18 12:13:32',
                'value': '2012-02-18 08:13:32'
            },
            'name': {
                'display_value': "MacBook Air 13\"",
                'value': "MacBook Air 13\""
            }
        },
        {
            'sys_class_name': {
                'display_value': 'Computer',
                'value': 'cmdb_ci_computer'
            },
            'sys_id': {
                'display_value': '00a9e80d3790200044e0bfc8bcbe5d42',
                'value': '00a9e80d3790200044e0bfc8bcbe5d42'
            },
            'sys_created_on': {
                'display_value': '2012-02-18 12:13:48',
                'value': '2012-02-18 08:13:48'
            },
            'name': {
                'display_value': "MacBook Air 17\"",
                'value': "MacBook Air 17\""
            }
        },
        {
            'sys_class_name': {
                'display_value': 'Computer',
                'value': 'cmdb_ci_computer'
            },
            'sys_id': {
                'display_value': '01a9e40d3790200044e0bfc8bcbe5dab',
                'value': '01a9e40d3790200044e0bfc8bcbe5dab'
            },
            'sys_created_on': {
                'display_value': '2012-02-18 12:12:30',
                'value': '2012-02-18 08:12:30'
            },
            'name': {
                'display_value': 'ThinkStation C20',
                'value': 'ThinkStation C20'
            }
        },
        {
            'sys_class_name': {
                'display_value': 'Computer',
                'value': 'cmdb_ci_computer'
            },
            'sys_id': {
                'display_value': '01a9ec0d3790200044e0bfc8bcbe5dc3',
                'value': '01a9ec0d3790200044e0bfc8bcbe5dc3'
            },
            'sys_created_on': {
                'display_value': '2012-02-18 12:14:42',
                'value': '2012-02-18 08:14:42'
            },
            'name': {
                'display_value': 'ThinkStation C20',
                'value': 'ThinkStation C20'
            }
        }
    ]
}

mock_collect_filter_components = {
    'result': [
        {
            'sys_class_name': {
                'display_value': 'Cluster',
                'value': 'cmdb_ci_cluster'
            },
            'sys_id': {
                'display_value': '00a96c0d3790200044e0bfc8bcbe5db4',
                'value': '00a96c0d3790200044e0bfc8bcbe5db4'
            },
            'sys_created_on': {
                'display_value': '2012-02-18 22:14:21',
                'value': '2012-02-18 18:14:21'
            },
            'name': {
                'display_value': 'Test Cluster',
                'value': 'Test Cluster'
            }
        }
    ]
}

# Mock response from ServiceNow API for relation between components
mock_relation_components = {
    'result': [
        {
            'type': {
                'link': 'https://instance.service-now.com/api/now/table/cmdb_rel_type/1a9cb166f1571100a92eb60da2bc',
                'value': '1a9cb166f1571100a92eb60da2bce5c5',
                'display_value': 'Cools'
            },
            'parent': {
                'link': 'https://instance.service-now.com/api/now/table/cmdb_ci/451047c6c0a8016400de0ae6df9b9d76',
                'value': '451047c6c0a8016400de0ae6df9b9d76',
                'display_value': 'some name'
            },
            'child': {
                'link': 'https://instance.service-now.com/api/now/table/cmdb_ci/53979c53c0a801640116ad2044643fb2',
                'value': '53979c53c0a801640116ad2044643fb2',
                'display_value': 'my name'
            }
        }
    ]
}

# Mock response from ServiceNow API for relation between components
mock_relation_with_filter = {
    'result': [
        {
            'type': {
                'link': 'https://instance.service-now.com/api/now/table/cmdb_rel_type/1a9cb166f1571100a92eb60da2bce5c5',
                'value': '1a9cb166f1571100a92eb60da2bce5c5',
                'display_value': 'Cools'
            },
            'parent': {
                'link': 'https://instance.service-now.com/api/now/table/cmdb_ci/451047c6c0a8016400de0ae6df9b9d76',
                'value': '451047c6c0a8016400de0ae6df9b9d76'
            },
            'child': {
                'link': 'https://instance.service-now.com/api/now/table/cmdb_ci/53979c53c0a801640116ad2044643fb2',
                'value': '53979c53c0a801640116ad2044643fb2'
            }
        }
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
    'url': "https://instance.service-now.com",
    'user': 'name',
    'password': 'secret'
}

state = State({'latest_sys_updated_on': "2017-06-29 11:03:27"})

instance_info = InstanceInfo(
    {
        'instance_tags': [],
        'url': mock_instance.get('url'),
        'user': mock_instance.get('user'),
        'password': mock_instance.get('password'),
        'include_resource_types': [],
        'batch_size': 100,
        'timeout': 10
    }
)


def mock_get_json(url, timeout, params, auth=None, verify=True, cert=None):
    """Mock method that returns params generated for use in _get_json_batch"""
    return params


@pytest.mark.usefixtures("instance")
class TestServicenow(unittest.TestCase):
    """Basic Test for servicenow integration."""

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        self.check = ServiceNowCheck('servicenow', {}, {}, [self.instance])
        topology.reset()
        aggregator.reset()
        telemetry.reset()
        self.check.commit_state(None)

    def test_check(self):
        """
        Testing Servicenow check.
        """
        self.check._collect_relation_types = mock_collect_process
        self.check._batch_collect = mock_collect_process

        self.check.run()

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 0)

        self.assertEqual(self.check._get_instance_key(),
                         TopologyInstance('servicenow_cmdb', 'https://instance.service-now.com'))

        AgentIntegrationTestUtil.assert_integration_snapshot(self.check,
                                                             'servicenow_cmdb:https://instance.service-now.com')

    def test_when_check_has_exception_stop_snapshot_is_false(self):
        """
        Test to raise a check exception when collecting components
        """
        self.check._get_json = mock.MagicMock()
        self.check._get_json.side_effect = Exception("Test exception occurred")
        self.check.run()

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
        self.check._batch_collect_components = mock.MagicMock()
        self.check._batch_collect_components.return_value = mock_collect_components
        self.check._batch_collect_components.__name__ = 'mock_batch_collect_components'
        self.check._batch_collect(self.check._batch_collect_components, instance_info)
        self.check._process_components(instance_info)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 1)
        self.assertEqual(len(topo_instances['relations']), 0)
        self.assertEqual(topo_instances['components'][0]['type'], 'cmdb_ci_computer')
        self.assertEqual(topo_instances['components'][0]['data']['identifiers'],
                         ["urn:host:/MacBook Pro 15",
                          "00a96c0d3790200044e0bfc8bcbe5db4",
                          "urn:host:/macbook pro 15",
                          "lupulus"])
        self.assertNotIn('stackstate-identifier:lupulus', topo_instances['components'][0]['data']['tags'])
        self.assertIn('stackstate', topo_instances['components'][0]['data']['tags'])

    def test_collect_relations(self):
        """
        Test to raise a check Exception while collecting component relations from ServiceNow API
        """
        self.assertRaises(Exception, self.check._batch_collect_relations, instance_info, 10, 0, 100)

    def test_process_relations(self):
        """
        Test to collect the component relations and process it as a topology
        """
        self.check._batch_collect_relations = mock.MagicMock()
        self.check._batch_collect_relations.return_value = mock_relation_components
        self.check._batch_collect_relations.__name__ = 'mock_batch_collect_relations'
        self.check._process_relations(instance_info)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(topo_instances['relations'][0]['type'], 'Cools')

    def test_process_components_with_sys_filter_change(self):
        """
        Test _process_components to return whole topology when query changed in between
        """
        sys_class_filter = self.instance.get('include_resource_types')
        instance_info.sys_class_filter = sys_class_filter
        query_filter = self.check._get_sys_class_component_filter_query(sys_class_filter)
        expected_query = 'sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server'
        # asserting the actual query
        self.assertEqual(expected_query, query_filter)

        self.check._get_sys_class_component_filter_query = mock.MagicMock()
        # changing the query in between and returning with incorrect query
        self.check._get_sys_class_component_filter_query.return_value = "sys_class_namecmdb_ci_netgear" \
                                                                        "%2Ccmdb_ci_cluster%2Ccmdb_ci_app_server"
        self.check._get_json = mock.MagicMock()
        self.check._get_json.return_value = mock_collect_components
        self.check._process_components(instance_info)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 1)
        self.assertEqual(len(topo_instances['relations']), 0)
        self.assertEqual(topo_instances['components'][0]['type'], 'cmdb_ci_computer')

    def test_process_component_relations_with_sys_filter_change(self):
        """
        Test _process_components to return whole topology when query changed in between
        """
        sys_class_filter = self.instance.get('include_resource_types')
        instance_info.sys_class_filter = sys_class_filter
        query_filter = self.check._get_sys_class_relation_filter_query(sys_class_filter)
        expected_query = 'parent.sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server' \
                         '^child.sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server'
        # asserting the actual query
        self.assertEqual(expected_query, query_filter)

        self.check._get_sys_class_relation_filter_query = mock.MagicMock()
        # changing the query in between and returning with incorrect query
        self.check._get_sys_class_relation_filter_query.return_value = "parent.sys_class_nameN" \
                                                                       "cmdb_ci_netgear%5Echild.sys_class_nameIN" \
                                                                       "cmdb_ci_netgear"
        self.check._get_json = mock.MagicMock()
        self.check._get_json.return_value = mock_relation_components
        self.check._process_relations(instance_info)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 1)
        self.assertEqual(topo_instances['relations'][0]['type'], 'Cools')

    def test_process_components_without_sys_filter_change(self):
        """
        Test _process_components to return whole topology when query changed in between
        """
        sys_class_filter = self.instance.get('include_resource_types')
        instance_info.sys_class_filter = sys_class_filter
        query_filter = self.check._get_sys_class_component_filter_query(sys_class_filter)
        expected_query = 'sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server'
        # asserting the actual query
        self.assertEqual(expected_query, query_filter)

        self.check._get_json = mock.MagicMock()
        self.check._get_json.return_value = mock_collect_filter_components
        self.check._process_components(instance_info)

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
        instance_info.sys_class_filter = sys_class_filter
        query_filter = self.check._get_sys_class_relation_filter_query(sys_class_filter)
        expected_query = 'parent.sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server' \
                         '^child.sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server'
        # asserting the actual query
        self.assertEqual(expected_query, query_filter)

        self.check._get_json = mock.MagicMock()
        self.check._get_json.return_value = mock_relation_with_filter

        self.check._process_relations(instance_info)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        # Since the filter gets specific relation only so returned one relation for filtered resource types
        self.assertEqual(len(topo_instances['relations']), 1)
        self.assertEqual(topo_instances['relations'][0]['type'], 'Cools')

    def test_batch_collect(self):
        """
        Test batch collecting components
        """
        self.check._batch_collect_components = mock.MagicMock()
        self.check._batch_collect_components.side_effect = [mock_collect_components_batch, mock_collect_components]
        self.check._batch_collect_components.__name__ = 'mock_batch_collect_components'
        new_inst_conf = copy(instance_info)
        new_inst_conf.batch_size = 5
        self.check._process_components(new_inst_conf)
        topology_instance = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topology_instance['components']), 6)

    def test_mandatory_instance_values(self):
        """
        Test existence of mandatory instance values
        """
        tests = [
            {
                'instance': {'user': 'name', 'password': 'secret'},
                'error': '{"url": ["This field is required."]}'
            },
            {
                'instance': {'user': 'name', 'url': "https://website.com"},
                'error': '{"password": ["This field is required."]}'
            },
            {
                'instance': {'password': 'secret', 'url': "https://website.com"},
                'error': '{"user": ["This field is required."]}'
            }
        ]
        for test in tests:
            check = ServiceNowCheck('servicenow', {}, {}, [test['instance']])
            result = json.loads(check.run())
            self.assertEqual(test['error'], result[0]['message'])

    def test_collect_components_returns_no_result(self):
        """Test if collect component returns no result or its not list"""
        self.check._batch_collect_components = mock.MagicMock()
        self.check._batch_collect_components.return_value = {}
        self.assertRaises(
            CheckException, self.check._batch_collect, self.check._batch_collect_components, instance_info
        )

    def test_collect_components_returns_empty_result(self):
        """Test if collect component returns no result or its not list"""
        self.check._batch_collect_components = mock.MagicMock()
        self.check._batch_collect_components.return_value = mock_empty_result
        self.check._batch_collect_components.__name__ = 'mock_batch_collect_components'
        self.check._batch_collect(self.check._batch_collect_components, instance_info)

        # no snapshot is created
        self.assertRaises(KeyError, topology.get_snapshot, self.check.check_id)

    def test_batch_collect_exact_result_as_batch_size(self):
        """
        Test batch collecting components
        """
        self.check._batch_collect_components = mock.MagicMock()
        self.check._batch_collect_components.side_effect = [mock_collect_components_batch, mock_empty_result]
        self.check._batch_collect_components.__name__ = 'mock_batch_collect_components'
        new_inst_conf = copy(instance_info)
        new_inst_conf.batch_size = 5
        self.check._process_components(new_inst_conf)

        topology_instance = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topology_instance['components']), 5)

    def test_batch_size(self):
        """
        Test max batch size value
        """
        instance = {'user': 'name', 'password': 'secret', 'url': "https://website.com", 'batch_size': 20000}
        check = ServiceNowCheck('servicenow', {}, {}, [instance])
        result = json.loads(check.run())
        self.assertEqual('{"batch_size": ["Int value should be less than or equal to 10000."]}', result[0]['message'])

    @mock.patch('requests.Session.get')
    def test_get_json_timeout(self, mock_request_get):
        """
        Test timeout exception exception gets critical service check
        """
        mock_request_get.side_effect = requests.exceptions.Timeout
        check = ServiceNowCheck('servicenow', {}, {}, [mock_instance])
        check.run()
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_NAME)
        self.assertEqual(1, len(service_checks))
        self.assertEqual(self.check.SERVICE_CHECK_NAME, service_checks[0].name)
        self.assertEqual(AgentCheck.CRITICAL, service_checks[0].status)
        self.assertEqual('Timeout: ', service_checks[0].message)
        self.check.commit_state(None)

    @mock.patch('requests.Session.get')
    def test_get_json_error_msg(self, mock_request_get):
        """
        Test malformed json error message
        """
        url, auth = self._get_url_auth()
        mock_request_get.return_value = mock.MagicMock(status_code=200, text=mock_result_with_malformed_str,
                                                       url='http://test.org')
        msg_py3 = 'Json parse error: "Expecting property name enclosed in double quotes: ' \
                  'line 11 column 5 (char 232)" in response from url http://test.org'
        msg_py2 = 'Json parse error: "Expecting property name: ' \
                  'line 11 column 5 (char 232)" in response from url http://test.org'
        expected_msg = msg_py3 if PY3 else msg_py2
        with self.assertRaises(CheckException) as context:
            self.check._get_json(url, 10, {}, auth)
        self.assertEqual(expected_msg, str(context.exception))

    def test_process_components_encoding_errors(self):
        """
        This would provoke following error with py27:
        "UnicodeEncodeError: 'ascii' codec can't encode character u'\xeb' in position 4: ordinal not in range(128)"
        in the function stackstate_checks.base.Identifiers.create_host_identifier
        """
        collect_components_with_fqdn_umlaut = {
            'result': [
                {
                    'sys_class_name': {
                        'display_value': 'cmdb_ci_computer',
                        'value': 'Computer'
                    },
                    'sys_id': {
                        'display_value': '00a96c0d3790200044e0bfc8bcbe5db4',
                        'value': '00a96c0d3790200044e0bfc8bcbe5db4'
                    },
                    'sys_created_on': {
                        'display_value': '2012-02-18 08:14:21',
                        'value': '2012-02-18 08:14:21'
                    },
                    'name': {
                        'display_value': 'Some computer',
                        'value': 'Some computer'
                    },
                    'fqdn': {
                        'display_value': u'abcdë.com',
                        'value': u'abcdë.com'
                    }
                }
            ]
        }
        self.check._batch_collect_components = mock.MagicMock()
        self.check._batch_collect_components.return_value = collect_components_with_fqdn_umlaut
        self.check._batch_collect_components.__name__ = 'mock_batch_collect_components'
        self.check._batch_collect(self.check._batch_collect_components, instance_info)
        self.check._process_components(instance_info)
        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(
            ['urn:host:/abcdë.com', 'urn:host:/Some computer', '00a96c0d3790200044e0bfc8bcbe5db4',
             'urn:host:/some computer'],
            topo_instances['components'][0]['data']['identifiers']
        )

    def test_batch_collect_components_sys_filter_with_query_filter(self):
        """
        Test the query filter with resource types while collecting components batch
        """
        self.check._get_json = mock_get_json
        instance_info['cmdb_ci_sysparm_query'] = "company.nameSTARTSWITHaxa"
        instance_info['include_resource_types'] = ['cmdb_ci_netgear']
        instance_info.batch_size = 100
        params = self.check._batch_collect_components(instance_info, 0)
        self.assertEqual(params.get("sysparm_offset"), 0)
        self.assertEqual(params.get('sysparm_limit'), 100)
        self.assertEqual(params.get('sysparm_query'), "sys_class_nameINcmdb_ci_netgear^company.nameSTARTSWITHaxa"
                                                      "^ORDERBYsys_created_on")

    def test_batch_collect_relations_sys_filter_with_query_filter(self):
        """
        Test the query filter with resource types while collecting relations batch
        """
        self.check._get_json = mock_get_json
        instance_info['cmdb_ci_sysparm_query'] = None
        instance_info['cmdb_rel_ci_sysparm_query'] = "parent.company.nameSTARTSWITHaxa^" \
                                                     "ORchild.company.nameSTARTSWITHaxa"
        instance_info['include_resource_types'] = ['cmdb_ci_netgear']
        instance_info.batch_size = 100
        params = self.check._batch_collect_relations(instance_info, 0)
        self.assertEqual(params.get("sysparm_offset"), 0)
        self.assertEqual(params.get('sysparm_limit'), 100)
        self.assertEqual(params.get('sysparm_query'), "parent.sys_class_nameINcmdb_ci_netgear^child.sys_class_nameIN"
                                                      "cmdb_ci_netgear^parent.company.nameSTARTSWITHaxa"
                                                      "^ORchild.company.nameSTARTSWITHaxa^ORDERBYsys_created_on")

    def test_collect_change_requests_sys_filter_with_query_filter(self):
        """
        Test the query filter with resource types while collecting change requests
        """
        self.check._get_json = mock_get_json
        instance_info['change_request_sysparm_query'] = "company.nameSTARTSWITHaxa"
        instance_info['include_resource_types'] = ['cmdb_ci_netgear']
        instance_info['state'] = state
        params = self.check._collect_change_requests_updates(instance_info)
        self.assertEqual(params.get("sysparm_display_value"), 'all')
        self.assertEqual(params.get("sysparm_exclude_reference_link"), 'true')
        self.assertEqual(params.get('sysparm_limit'), 1000)
        self.assertEqual(params.get('sysparm_query'), "sys_updated_on>javascript:gs.dateGenerate('2017-06-29', "
                                                      "'11:03:27')^company.nameSTARTSWITHaxa")

    def _get_url_auth(self):
        url = "{}/api/now/table/cmdb_ci".format(self.instance.get('url'))
        auth = (self.instance.get('user'), self.instance.get('password'))
        return url, auth

    @staticmethod
    def _read_data(filename):
        path_to_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', filename)
        with open(path_to_file, "r") as f:
            return json.load(f)
