from stackstate_checks.base.utils.common import read_file, load_json_from_file
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

    synthetic_monitors = load_json_from_file("sythetic_monitoring_response.json", "samples")['monitors']
    dynatrace_components = test_topology['components']

    # Check that a DynaTrace component does not create relations
    assert test_topology['relations'] == []
    # Check that the number of components in the topology matches the number of synthetic monitors returned by DynaTrace
    assert len(dynatrace_components) == len(synthetic_monitors)

    # Check that the dynatrace component data matches the synthetic monitor data returned by DynaTrace
    for dynatrace_component, synthetic_monitor in zip(dynatrace_components, synthetic_monitors):
        assert dynatrace_component['id'] == synthetic_monitor['entityId']
        assert dynatrace_component['type'] == 'synthetic-monitor'
        assert dynatrace_component['data']['name'] == synthetic_monitor['name']
        assert dynatrace_component['data']['type'] == synthetic_monitor['type']
        assert dynatrace_component['data']['entityId'] == synthetic_monitor['entityId']
        assert dynatrace_component['data']['enabled'] == str(synthetic_monitor['enabled'])
