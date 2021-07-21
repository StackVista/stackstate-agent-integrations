import mock
import requests_mock

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.stubs import aggregator, topology
from .helpers import read_file
from .test_dynatrace_event import CHECK_NAME


def test_tags(dynatrace_check, test_instance):
    dynatrace_check._current_time_seconds = mock.MagicMock(return_value=1613485584)
    url = test_instance['url']
    timestamp = dynatrace_check._generate_bootstrap_timestamp(test_instance['events_boostrap_days'])
    with requests_mock.Mocker() as m:
        m.get("{}/api/v1/entity/infrastructure/hosts".format(url), status_code=200,
              text=read_file('HOST-9106C06F228CEC6B.json'))
        m.get("{}/api/v1/entity/applications".format(url), status_code=200, text='[]')
        m.get("{}/api/v1/entity/services".format(url), status_code=200, text='[]')
        m.get("{}/api/v1/entity/infrastructure/processes".format(url), status_code=200, text='[]')
        m.get("{}/api/v1/entity/infrastructure/process-groups".format(url), status_code=200, text='[]')
        m.get("{}/api/v2/entities".format(url), status_code=200, text='[]')
        m.get('{}/api/v1/events?from={}'.format(url, timestamp), status_code=200, text='[]')
        dynatrace_check.run()
        aggregator.assert_service_check(CHECK_NAME, count=1, status=AgentCheck.OK)
        components = topology.get_snapshot('')['components']
        assert components[0]['data']['environments'] == ['test-environment']
        assert components[0]['data']['domain'] == 'test-domain'
        assert components[0]['data']['layer'] == 'test-layer'
        assert 'test-identifier' in components[0]['data']['identifiers']
