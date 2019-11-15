from stackstate_checks.cloudera import Cloudera


def test_check_collect_cluster(aggregator, instance_dev):
    check = Cloudera('test', {}, {})
    check.check(instance_dev)

    aggregator.assert_all_metrics_covered()
