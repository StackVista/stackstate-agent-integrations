import pytest
from stackstate_checks.splunk_health.splunk_health import SplunkHealth
from stackstate_checks.dev import WaitFor


@pytest.mark.integration
@pytest.mark.usefixtures('test_environment')
def test_health_search(health, splunk_health_instance):
    check = SplunkHealth("splunk", {}, {}, [splunk_health_instance])

    def run_and_check():
        health.reset()
        assert check.run() == ''
        health.assert_snapshot(check.check_id, check.health.stream,
                               {'expiry_interval_s': 0, 'repeat_interval_s': 15}, {},
                               [{'checkStateId': u'disk_sdb',
                                 'health': 'CRITICAL',
                                 'name': u'Disk sdb',
                                 'topologyElementIdentifier': u'component2'},
                                {'checkStateId': u'disk_sda',
                                 'health': 'CLEAR',
                                 'message': u'sda message',
                                 'name': u'Disk sda',
                                 'topologyElementIdentifier': u'component1'}
                                ])

    assert WaitFor(run_and_check, attempts=10)() is True
