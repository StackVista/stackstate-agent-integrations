from freezegun import freeze_time

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.common import read_file
from stackstate_checks.servicenow.servicenow import API_SNOW_TABLE_CHANGE_REQUEST, API_SNOW_TABLE_CMDB_CI, \
    API_SNOW_TABLE_CMDB_REL_CI
from stackstate_checks.stubs import aggregator, telemetry

SERVICE_CHECK_NAME = 'servicenow.cmdb.topology_information'
EMPTY_RESULT = '{"result": []}'
DEFAULT_CR_RESPONSE = [
    {'status_code': 200, 'text': EMPTY_RESULT},
    {'status_code': 200, 'text': read_file('planned_crs.json', 'samples')},
    {'status_code': 200, 'text': EMPTY_RESULT},
    {'status_code': 200, 'text': read_file('planned_crs.json', 'samples')},
]


@freeze_time("2021-08-02 12:15:00")
def test_two_planned_crs_one_matches_resend_schedule(servicenow_check, requests_mock, test_cr_instance):
    request_mock_cmdb_ci_tables_setup(requests_mock, test_cr_instance.get('url'), DEFAULT_CR_RESPONSE)
    servicenow_check.run()
    aggregator.assert_service_check(SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_events = telemetry._topology_events
    assert len(topology_events) == 1
    assert topology_events[0]['msg_title'] == 'CHG0040004: Please reboot AS400'
    state = servicenow_check.state_manager.get_state(servicenow_check._get_state_descriptor())
    assert ['CHG0040004'] == state.get('sent_planned_crs_cache')


def test_planned_cr_is_removed_from_sent_cache_after_end_time(servicenow_check, requests_mock, test_cr_instance):
    request_mock_cmdb_ci_tables_setup(requests_mock, test_cr_instance.get('url'), DEFAULT_CR_RESPONSE)

    with freeze_time('2021-08-02 12:15:00'):
        servicenow_check.run()
        aggregator.assert_service_check(SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
        topology_events = telemetry._topology_events
        assert len(topology_events) == 1
        state = servicenow_check.state_manager.get_state(servicenow_check._get_state_descriptor())
        assert ['CHG0040004'] == state.get('sent_planned_crs_cache')

    with freeze_time('2021-08-02 15:00:00'):
        servicenow_check.run()
        aggregator.assert_service_check(SERVICE_CHECK_NAME, count=2, status=AgentCheck.OK)
        topology_events = telemetry._topology_events
        assert len(topology_events) == 1
        state = servicenow_check.state_manager.get_state(servicenow_check._get_state_descriptor())
        assert [] == state.get('sent_planned_crs_cache')


@freeze_time('2021-08-02 11:15:00')
def test_change_of_planned_cr_resend_schedule(servicenow_check, requests_mock, test_cr_instance):
    test_cr_instance['planned_change_request_resend_schedule'] = 2
    request_mock_cmdb_ci_tables_setup(requests_mock, test_cr_instance.get('url'), DEFAULT_CR_RESPONSE)
    servicenow_check.run()
    aggregator.assert_service_check(SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_events = telemetry._topology_events
    assert len(topology_events) == 2
    assert topology_events[0]['msg_title'] == 'CHG0040007: Please reboot ApplicationServerPeopleSoft'
    assert topology_events[1]['msg_title'] == 'CHG0040004: Please reboot AS400'
    state = servicenow_check.state_manager.get_state(servicenow_check._get_state_descriptor())
    assert ['CHG0040007', 'CHG0040004'] == state.get('sent_planned_crs_cache')


@freeze_time('2021-09-01 11:15:00')
def test_cr_custom_fields(servicenow_check, requests_mock, test_cr_instance):
    test_cr_instance['custom_planned_start_date_field'] = 'u_custom_start_date'
    test_cr_instance['custom_planned_end_date_field'] = 'u_custom_end_date'
    response = [{'status_code': 200, 'text': EMPTY_RESULT},
                {'status_code': 200, 'text': read_file('CHG0040007_custom_cr_fields.json', 'samples')}]
    request_mock_cmdb_ci_tables_setup(requests_mock, test_cr_instance.get('url'), response)
    servicenow_check.run()
    aggregator.assert_service_check(SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    topology_events = telemetry._topology_events
    assert len(topology_events) == 1
    assert topology_events[0]['msg_title'] == 'CHG0040007: Please reboot ApplicationServerPeopleSoft'
    assert topology_events[0]['context']['data']['start_date'] == '2021-09-01 11:30:00'
    assert topology_events[0]['context']['data']['end_date'] == '2021-09-01 12:00:00'


def request_mock_cmdb_ci_tables_setup(requests_mock, url, response):
    api_cmdb_ci_url = url + API_SNOW_TABLE_CMDB_CI
    api_cmdb_ci_rel_url = url + API_SNOW_TABLE_CMDB_REL_CI
    api_cr_url = url + API_SNOW_TABLE_CHANGE_REQUEST
    requests_mock.register_uri('GET', api_cmdb_ci_url, status_code=200, text=EMPTY_RESULT)
    requests_mock.register_uri('GET', api_cmdb_ci_rel_url, status_code=200, text=EMPTY_RESULT)
    requests_mock.register_uri('GET', api_cr_url, response)
