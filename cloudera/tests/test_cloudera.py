from stackstate_checks.cloudera import Cloudera


def test_check_collect_cluster(aggregator, instance):
    check = Cloudera('test', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
