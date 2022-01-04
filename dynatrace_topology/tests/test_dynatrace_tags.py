from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.common import read_file
from .conftest import set_http_responses


def test_tags(dynatrace_check, requests_mock, aggregator, topology):
    """
    Testing do dynatrace tags finish in right places
    """
    set_http_responses(requests_mock, hosts=read_file('HOST-9106C06F228CEC6B.json', 'samples'))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    components = topology.get_snapshot(dynatrace_check.check_id)['components']
    assert components[0]['data']['environments'] == ['test-environment']
    assert components[0]['data']['domain'] == 'test-domain'
    assert components[0]['data']['layer'] == 'test-layer'
    assert 'test-identifier' in components[0]['data']['identifiers']
