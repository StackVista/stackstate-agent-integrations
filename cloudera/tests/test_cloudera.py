# from stackstate_checks.base.stubs import topology
# from stackstate_checks.cloudera import Cloudera


# try:
# from urlparse import urlparse
# except ModuleNotFoundError:
#     from urllib.parse import urlparse


def test_check_collect_cluster(aggregator, instance):
    # TODO finish unittest
    pass

#
#    check = Cloudera('test', {}, {}, instances=[instance])
#    check.check(instance)
#
#    snapshot = topology.get_snapshot('')
#    instance_url = urlparse(instance['url']).netloc
#    assert snapshot['instance_key']['url'] == instance_url
#    assert len(snapshot['components']) == 40
#    assert len(snapshot['relations']) == 39
#
#    aggregator.assert_all_metrics_covered()
