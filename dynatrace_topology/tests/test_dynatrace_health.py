from stackstate_checks.base import AgentCheck

from stackstate_checks.base.utils.common import read_file
from .conftest import set_http_responses


def test_health(dynatrace_check, requests_mock, test_instance, aggregator, health):
    """
    Test if we have Dynatrace monitored health state for each component.
    """
    set_http_responses(requests_mock, hosts=read_file('host_response.json', 'samples'))
    assert dynatrace_check.run() == ""
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[{'checkStateId': 'HOST-6AAE0F78BCF2E0F4',
                                          'health': 'CLEAR',
                                          'message': 'EX01.stackstate.lab is monitored by Dynatrace',
                                          'name': 'Dynatrace monitored',
                                          'topologyElementIdentifier': 'urn:dynatrace:/HOST-6AAE0F78BCF2E0F4'},
                                         {'checkStateId': 'HOST-AA6A5D81A0006807',
                                          'health': 'CLEAR',
                                          'message': 'SQL01.stackstate.lab is monitored by Dynatrace',
                                          'name': 'Dynatrace monitored',
                                          'topologyElementIdentifier': 'urn:dynatrace:/HOST-AA6A5D81A0006807'}],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                           stop_snapshot={})
