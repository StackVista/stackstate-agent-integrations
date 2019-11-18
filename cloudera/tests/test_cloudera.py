from stackstate_checks.base.stubs import topology
from stackstate_checks.cloudera import Cloudera


def test_check_collect_cluster(aggregator, instance_dev):
    check = Cloudera('test', {}, {}, instances=[instance_dev])
    check.check(instance_dev)

    snapshot = topology.get_snapshot('')
    assert snapshot['instance_key']['url'] == instance_dev['url']
    assert len(snapshot['components']) == 20
    assert len(snapshot['relations']) == 17

    aggregator.assert_all_metrics_covered()
