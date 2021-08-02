from stackstate_checks.base import AgentCheck
from stackstate_checks.stubs import aggregator

from stackstate_checks.base.utils.common import read_file
from stackstate_checks.servicenow.servicenow import API_SNOW_TABLE_CHANGE_REQUEST, API_SNOW_TABLE_CMDB_CI, \
    API_SNOW_TABLE_CMDB_REL_CI

SERVICE_CHECK_NAME = "servicenow.cmdb.topology_information"


def test_planned_crs(servicenow_check, requests_mock, test_cr_instance):
    url = test_cr_instance.get('url')
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    requests_mock.register_uri('GET', api_cmdb_ci_url, status_code=200, text='{"result": []}')
    api_cmdb_ci_rel_url = url + API_SNOW_TABLE_CMDB_REL_CI
    requests_mock.register_uri('GET', api_cmdb_ci_rel_url, status_code=200, text='{"result": []}')
    api_cr_url = url + API_SNOW_TABLE_CHANGE_REQUEST
    requests_mock.register_uri('GET', api_cr_url, [
        {'status_code': 200, 'text': read_file('CHG0040007.json', 'samples')},
        {'status_code': 200, 'text': read_file('planned_crs.json', 'samples')}
    ])
    servicenow_check.run()
    aggregator.assert_service_check(SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
