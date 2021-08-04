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
