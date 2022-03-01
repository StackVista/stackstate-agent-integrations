from stackstate_checks.base.utils.common import read_file
from .conftest import set_http_responses
from stackstate_checks.base import AgentCheck


def test_synthetic_monitor(dynatrace_check, requests_mock, topology, aggregator):
    """
    Testing Dynatrace check should collect syntethic monitor
    """
    set_http_responses(requests_mock, monitors=read_file("sythetic_monitoring_response.json", "samples"))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    test_topology = topology.get_snapshot(dynatrace_check.check_id)
    dynatrace_component = test_topology['components'][0]
    assert dynatrace_component['id'] == 'SYNTHETIC_TEST-31C5003C3C6342D0'
    assert dynatrace_component['type'] == 'monitor'
    assert dynatrace_component['data']['name'] == 'google.com'
    assert dynatrace_component['data']['entityId'] == 'SYNTHETIC_TEST-31C5003C3C6342D0'
    assert dynatrace_component['data']['type'] == 'BROWSER'
