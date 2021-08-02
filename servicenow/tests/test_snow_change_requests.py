from freezegun import freeze_time

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.common import read_file
from stackstate_checks.servicenow.servicenow import API_SNOW_TABLE_CHANGE_REQUEST, API_SNOW_TABLE_CMDB_CI, \
    API_SNOW_TABLE_CMDB_REL_CI
from stackstate_checks.stubs import aggregator, telemetry

SERVICE_CHECK_NAME = 'servicenow.cmdb.topology_information'
EMPTY_RESULT = '{"result": []}'


@freeze_time("2021-08-02 12:15:00")
def test_two_planned_crs_one_matches_resend_schedule(servicenow_check, requests_mock, test_cr_instance):
    url = test_cr_instance.get('url')
    request_mock_cmdb_ci_tables_setup(requests_mock, url)
    api_cr_url = url + API_SNOW_TABLE_CHANGE_REQUEST
    requests_mock.register_uri('GET', api_cr_url, [
        {'status_code': 200, 'text': EMPTY_RESULT},
        {'status_code': 200, 'text': read_file('planned_crs.json', 'samples')},
    ])
    servicenow_check.run()
    aggregator.assert_service_check(SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_events = telemetry._topology_events
    assert len(topology_events) == 1
    assert topology_events[0].get('msg_title') == 'CHG0040004: Please reboot AS400'


def request_mock_cmdb_ci_tables_setup(requests_mock, url):
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    api_cmdb_ci_rel_url = url + API_SNOW_TABLE_CMDB_REL_CI
    requests_mock.register_uri('GET', api_cmdb_ci_url, status_code=200, text=EMPTY_RESULT)
    requests_mock.register_uri('GET', api_cmdb_ci_rel_url, status_code=200, text=EMPTY_RESULT)
