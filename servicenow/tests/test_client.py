# -*- coding: utf-8 -*-

# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
from stackstate_checks.base.errors import CheckException

from stackstate_checks.base.utils.common import read_file
from stackstate_checks.servicenow.common import API_SNOW_TABLE_CMDB_CI


def test_append_to_sysparm_query(test_client):
    """
    Test append of sysparm_query to params dict and creation of new empty dict if we don't pass one as parameter.
    """
    params = test_client._params_append_to_sysparm_query(add_to_query='first_one')
    assert params == {'sysparm_query': 'first_one'}
    params = test_client._params_append_to_sysparm_query(params=params, add_to_query='second_one')
    assert params == {'sysparm_query': 'first_one^second_one'}
    params = test_client._params_append_to_sysparm_query(add_to_query='')
    assert params == {}


def test_json_batch_params(test_client):
    """
    Test json batch params
    """
    offset = 10
    batch_size = 200
    params = test_client._prepare_json_batch_params(params={}, offset=offset, batch_size=batch_size)
    assert params.get('sysparm_offset') == offset
    assert params.get('sysparm_limit') == batch_size
    assert params.get('sysparm_query') == 'ORDERBYsys_created_on'


def test_json_batch_adding_param(test_client):
    """
    Test batch path construction adding to sysparm_query
    """
    offset = 10
    batch_size = 200
    params = test_client._prepare_json_batch_params(params={'sysparm_query': 'company.nameSTARTSWITHaxa'},
                                                    offset=offset,
                                                    batch_size=batch_size)
    assert params.get('sysparm_offset') == offset
    assert params.get('sysparm_limit') == batch_size
    assert params.get('sysparm_query') == 'company.nameSTARTSWITHaxa^ORDERBYsys_created_on'


def test_get_sys_class_component_filter_query(test_client):
    """
    Test to check if the method creates the proper param query
    """
    sys_class_filter = ['cmdb_ci_netgear', 'cmdb_ci_cluster', 'cmdb_ci_app_server']
    query = test_client._get_sys_class_component_filter_query(sys_class_filter)
    assert query == 'sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server'


def test_get_sys_class_component_filter_query_only_one_element(test_client):
    """
    Test to check if the method creates the proper param query for only one element
    """
    sys_class_filter = ['cmdb_ci_app_server_java']
    query = test_client._get_sys_class_component_filter_query(sys_class_filter)
    assert query == 'sys_class_nameINcmdb_ci_app_server_java'


def test_get_sys_class_relation_filter_query(test_client):
    """
    Test to check if the method creates the proper param query
    """
    sys_class_filter = ['cmdb_ci_netgear', 'cmdb_ci_cluster', 'cmdb_ci_app_server']
    query = test_client._get_sys_class_relation_filter_query(sys_class_filter)
    expected_query = 'parent.sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server' \
                     '^child.sys_class_nameINcmdb_ci_netgear,cmdb_ci_cluster,cmdb_ci_app_server'
    assert query == expected_query


def test_get_sys_class_relation_filter_query_only_one_element(test_client):
    """
    Test to check if the method creates the proper param query for only one
    """
    sys_class_filter = ['cmdb_ci_app_server_java']
    query = test_client._get_sys_class_relation_filter_query(sys_class_filter)
    assert query == 'parent.sys_class_nameINcmdb_ci_app_server_java^child.sys_class_nameINcmdb_ci_app_server_java'


def test_get_json_utf_encoding(test_client, requests_mock, get_url_auth):
    """
    Test to check the method _get_json response with unicode character in name
    """
    url, auth = get_url_auth
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    requests_mock.get(url=api_cmdb_ci_url, status_code=200, text=read_file('cmdb_ci_result_with_utf8.json', 'samples'))
    response = test_client._get_json(api_cmdb_ci_url, timeout=10, params={}, auth=auth)
    assert response.get('result')[0].get('name') == u'Avery® Wizard 2.1 forMicrosoft® Word 2000'


def test_get_json_ok_status(test_client, requests_mock, get_url_auth):
    """
    Test to check the method _get_json with positive response and get a OK service check
    """
    url, auth = get_url_auth
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    requests_mock.get(url=api_cmdb_ci_url, status_code=200, text=read_file('cmdb_ci_result_200.json', 'samples'))
    response = test_client._get_json(api_cmdb_ci_url, timeout=10, params={}, auth=auth)
    assert response.get('result')[0].get('name') == 'Unknown'


def test_get_json_error_status(test_client, requests_mock, get_url_auth):
    """
    Test for Check Exception if response code is not 200
    """
    url, auth = get_url_auth
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    requests_mock.get(url=api_cmdb_ci_url, status_code=404,
                      text=read_file('cmdb_ci_result_error_message.json', 'samples'))
    with pytest.raises(CheckException) as e:
        test_client._get_json(api_cmdb_ci_url, timeout=10, params={}, auth=auth)
    assert 'Got status: 404 when hitting' in str(e)


def test_get_json_ok_status_with_error_in_response(test_client, requests_mock, get_url_auth):
    """
    Test for situation when we get error in json and request status is OK
    """
    url, auth = get_url_auth
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    requests_mock.get(url=api_cmdb_ci_url, status_code=200,
                      text=read_file('cmdb_ci_result_error_message.json', 'samples'))
    with pytest.raises(CheckException) as e:
        test_client._get_json(api_cmdb_ci_url, timeout=10, params={}, auth=auth)
    assert 'The resource you requested is not part of the API.' in str(e)


def test_get_json_malformed_json(test_client, requests_mock, get_url_auth):
    """
    Test just malformed json
    """
    url, auth = get_url_auth
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    requests_mock.get(url=api_cmdb_ci_url, status_code=200,
                      text=read_file('cmdb_ci_result_with_malformed_json.txt', 'samples'))
    with pytest.raises(CheckException) as e:
        test_client._get_json(api_cmdb_ci_url, timeout=10, params={}, auth=auth)
    assert 'Json parse error' in str(e)


def test_get_json_malformed_json_and_execution_time_exceeded_error(test_client, requests_mock, get_url_auth):
    """
    Test malformed json that sometimes happens with
    ServiceNow error 'Transaction cancelled: maximum execution time exceeded'
    """
    url, auth = get_url_auth
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    requests_mock.get(url=api_cmdb_ci_url, status_code=200,
                      text=read_file('cmdb_ci_result_malformed_json_with_error_msg.txt', 'samples'))
    with pytest.raises(CheckException) as e:
        test_client._get_json(api_cmdb_ci_url, timeout=10, params={}, auth=auth)
    assert 'Transaction cancelled: maximum execution time exceeded' in str(e)
