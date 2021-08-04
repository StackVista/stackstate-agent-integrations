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

# def test_get_json_utf_encoding(test_client, requests_mock, get_url_auth):
#     """
#     Test to check the method _get_json response with unicode character in name
#     """
#     url, auth = get_url_auth()
#     requests_mock.get(status_code=200, text=json.dumps(mock_result_with_utf8))
#     mock_req_get.return_value = mock.MagicMock(status_code=200, text=json.dumps(mock_result_with_utf8))
#     response = self.check._get_json(url, timeout=10, params={}, auth=auth)
#     self.assertEqual(u'Avery® Wizard 2.1 forMicrosoft® Word 2000', response.get('result').get('name'))
#
# @mock.patch('requests.Session.get')
# def test_get_json_malformed_json(self, mock_request_get):
#     """
#     Test just malformed json
#     """
#     url, auth = self._get_url_auth()
#     mock_request_get.return_value = mock.MagicMock(status_code=200, text=mock_result_with_malformed_str)
#     self.assertRaises(CheckException, self.check._get_json, url, 10, auth)
#
# @mock.patch('requests.Session.get')
# def test_get_json_malformed_json_and_execution_time_exceeded_error(self, mock_request_get):
#     """
#     Test malformed json that sometimes happens with
#     ServiceNow error 'Transaction cancelled: maximum execution time exceeded'
#     """
#     url, auth = self._get_url_auth()
#     mock_request_get.return_value = mock.MagicMock(status_code=200, text=mock_result_malformed_str_with_error_msg)
#     self.assertRaises(CheckException, self.check._get_json, url, 10, auth)
#
