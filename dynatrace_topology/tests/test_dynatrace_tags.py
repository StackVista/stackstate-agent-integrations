from stackstate_checks.base import AgentCheck
from stackstate_checks.base.utils.common import read_file
from .conftest import set_http_responses


def test_tags(dynatrace_check, requests_mock, aggregator, topology):
    """
    Testing do dynatrace tags finish in right places
    """
    set_http_responses(requests_mock, hosts=read_file('HOST-27D021F0FED92055.json', 'samples'))
    dynatrace_check.run()
    aggregator.assert_service_check(dynatrace_check.SERVICE_CHECK_NAME, count=1, status=AgentCheck.OK)
    components = topology.get_snapshot(dynatrace_check.check_id)['components']
    assert components[0]['data']['environments'] == ['production']
    assert components[0]['data']['domain'] == 'dynatrace'
    assert components[0]['data']['entityId'] == 'HOST-27D021F0FED92055'
    assert 'urn:dynatrace:/HOST-27D021F0FED92055' in components[0]['data']['identifiers']
