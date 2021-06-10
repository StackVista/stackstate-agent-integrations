import pytest
from stackstate_checks.splunk_topology.splunk_topology import SplunkTopology
from stackstate_checks.dev import WaitFor
from .common import HOST


@pytest.mark.integration
@pytest.mark.usefixtures('test_environment')
def test_component_search(topology, splunk_components_instance):
    check = SplunkTopology("splunk", {}, {}, [splunk_components_instance])

    def run_and_check():
        topology.reset()
        assert check.run() == ''
        snapshot = topology.get_snapshot(check.check_id)
        del snapshot["components"][0]["data"]["_time"]
        del snapshot["components"][1]["data"]["_time"]
        topology.assert_snapshot(check.check_id, check.get_instance_key(splunk_components_instance), True, True,
                                 [{
                                     'id': u'server_2',
                                     'type': u'server',
                                     'data': {
                                         u"description": 'My important server 2',
                                         u"tags": ['integration-type:splunk',
                                                   'integration-url:http://%s:8089' % HOST,
                                                   'mytag', 'mytag2']
                                     }
                                 }, {
                                     'id': u'server_1',
                                     'type': u'server',
                                     'data': {
                                         u"description": 'My important server 1',
                                         u"tags": ['integration-type:splunk',
                                                   'integration-url:http://%s:8089' % HOST,
                                                   'mytag', 'mytag2']
                                     }
                                 }],
                                 [])

    assert WaitFor(run_and_check, attempts=10)() is True


@pytest.mark.integration
@pytest.mark.usefixtures('test_environment')
def test_relation_search(topology, splunk_relations_instance):
    check = SplunkTopology("splunk", {}, {}, [splunk_relations_instance])

    def run_and_check():
        topology.reset()
        assert check.run() == ''
        snapshot = topology.get_snapshot(check.check_id)
        del snapshot["relations"][0]["data"]["_time"]
        topology.assert_snapshot(check.check_id, check.get_instance_key(splunk_relations_instance), True, True,
                                 [],
                                 [{'type': u'CONNECTED',
                                   "source_id": u"server_1",
                                   "target_id": u"server_2",
                                   'data': {
                                       u"description": 'Some relation',
                                       u"tags": ['mytag', 'mytag2']
                                   }
                                   }])

    assert WaitFor(run_and_check, attempts=10)() is True
