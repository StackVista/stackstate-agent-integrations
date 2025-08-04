from stackstate_checks.base import AgentCheck

from stackstate_checks.base.utils.common import read_file
from .conftest import set_http_responses


def test_health(dynatrace_check, requests_mock, test_instance, aggregator, health):
    """
    Test if we have Dynatrace monitored health state for each component.
    """
    set_http_responses(requests_mock, hosts=read_file('host_response_v2.json', 'samples'))
    assert dynatrace_check.run() == ""
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    health.assert_snapshot(dynatrace_check.check_id, dynatrace_check.health.stream,
                           check_states=[{'checkStateId': 'HOST-27D021F0FED92055',
                                          'health': 'CLEAR',
                                          'message': 'ubuntu is monitored by Dynatrace',
                                          'name': 'Dynatrace monitored',
                                          'topologyElementIdentifier': 'urn:dynatrace:/HOST-27D021F0FED92055'},
                                         {'checkStateId': 'HOST-CCAF57403E126C46',
                                          'health': 'CLEAR',
                                          'message': 'ubuntu is monitored by Dynatrace',
                                          'name': 'Dynatrace monitored',
                                          'topologyElementIdentifier': 'urn:dynatrace:/HOST-CCAF57403E126C46'}],
                           start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                           stop_snapshot={})
