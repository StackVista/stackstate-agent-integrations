# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.openmetrics import OpenMetricsCheck
from stackstate_checks.base import AgentIntegrationInstance
import pytest
import mock
from prometheus_client import generate_latest, CollectorRegistry, Gauge, Counter, Histogram

CHECK_NAME = 'openmetrics'
NAMESPACE = 'openmetrics'

instance = {
    'prometheus_url': 'http://localhost:10249/metrics',
    'namespace': 'openmetrics',
    'metrics': [
        {'metric1': 'renamed.metric1'},
        'metric2',
        'counter1_total',
        'hist1'
    ],
    'send_histograms_buckets': True,
    'send_monotonic_counter': False
}


@pytest.fixture(scope='module', autouse=True)
def poll_mock():
    registry = CollectorRegistry()
    g1 = Gauge('metric1', 'processor usage', ['matched_label', 'node', 'flavor'], registry=registry)
    g1.labels(matched_label='foobar', node='host1', flavor='test').set(99.9)
    g2 = Gauge('metric2', 'memory usage', ['matched_label', 'node', 'timestamp'], registry=registry)
    g2.labels(matched_label='foobar', node='host2', timestamp='123').set(12.2)
    c1 = Counter('counter1', 'hits', ['node'], registry=registry)
    c1.labels(node='host2').inc(42)
    g3 = Gauge('metric3', 'memory usage', ['matched_label', 'node', 'timestamp'], registry=registry)
    g3.labels(matched_label='foobar', node='host2', timestamp='456').set(float('inf'))
    h1 = Histogram('hist1', 'latency', ['node'], buckets=[0.0, 1.0, "+Inf"], registry=registry)
    h1.labels(node='host2').observe(0.123)

    with mock.patch(
        'requests.get',
        return_value=mock.MagicMock(
            status_code=200,
            iter_lines=lambda **kwargs: generate_latest(registry).decode().split('\n'),
            headers={'Content-Type': 'text/plain'}
        )
    ):
        yield


def test_check_instance_key():
    check = OpenMetricsCheck('openmetrics', None, {}, [instance])
    assert check.get_instance_key(instance) == AgentIntegrationInstance('openmetrics', 'stubbed-cluster-name')


def test_openmetrics_check(aggregator):
    c = OpenMetricsCheck('openmetrics', None, {}, [instance])
    c.check(instance)
    aggregator.assert_metric(
        CHECK_NAME + '.renamed.metric1',
        tags=['node:host1', 'flavor:test', 'matched_label:foobar'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_metric(
        CHECK_NAME + '.metric2',
        tags=['timestamp:123', 'node:host2', 'matched_label:foobar'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_metric(
        CHECK_NAME + '.counter1',
        tags=['node:host2'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_metric(
        CHECK_NAME + '.hist1.bucket',
        tags=['node:host2', 'le:0.0'],
        metric_type=aggregator.GAUGE,
        value=0.0
    )
    aggregator.assert_metric(
        CHECK_NAME + '.hist1.bucket',
        tags=['node:host2', 'le:1.0'],
        metric_type=aggregator.GAUGE,
        value=1.0
    )
    aggregator.assert_metric(
        CHECK_NAME + '.hist1.bucket',
        tags=['node:host2', 'le:+Inf'],
        metric_type=aggregator.GAUGE,
    )
    aggregator.assert_metric(
        CHECK_NAME + '.hist1.count',
        tags=['node:host2'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_metric(
        CHECK_NAME + '.hist1.sum',
        tags=['node:host2'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_all_metrics_covered()


def test_openmetrics_check_counter_gauge(aggregator):
    instance['send_monotonic_counter'] = True
    c = OpenMetricsCheck('openmetrics', None, {}, [instance])
    c.check(instance)
    aggregator.assert_metric(
        CHECK_NAME + '.counter1',
        tags=['node:host2'],
        metric_type=aggregator.MONOTONIC_COUNT
    )


def test_invalid_metric(aggregator):
    """
    Testing that invalid values of metrics are discarded
    """
    bad_metric_instance = {
        'prometheus_url': 'http://localhost:10249/metrics',
        'namespace': 'openmetrics',
        'metrics': [
            {'metric1': 'renamed.metric1'},
            'metric2',
            'metric3'
        ],
        'send_histograms_buckets': True
    }
    c = OpenMetricsCheck('openmetrics', None, {}, [bad_metric_instance])
    c.check(bad_metric_instance)
    assert aggregator.metrics('metric3') == []


def test_openmetrics_wildcard(aggregator):
    instance_wildcard = {
        'prometheus_url': 'http://localhost:10249/metrics',
        'namespace': 'openmetrics',
        'metrics': ['metric*'],
    }

    c = OpenMetricsCheck('openmetrics', None, {}, [instance_wildcard])
    c.check(instance)
    aggregator.assert_metric(
        CHECK_NAME + '.metric1',
        tags=['node:host1', 'flavor:test', 'matched_label:foobar'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_metric(
        CHECK_NAME + '.metric2',
        tags=['timestamp:123', 'node:host2', 'matched_label:foobar'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_all_metrics_covered()


def test_openmetrics_default_instance(aggregator):
    """
    Testing openmetrics with default instance
    """

    c = OpenMetricsCheck(CHECK_NAME, None, {}, [], default_instances={
        'openmetrics': {
            'prometheus_url': 'http://localhost:10249/metrics',
            'namespace': 'openmetrics',
            'metrics': [
                {'metric1': 'renamed.metric1'},
                'metric2'
            ]
        }},
        default_namespace='openmetrics')
    c.check({
        'prometheus_url': 'http://custom:1337/metrics',
    })
    aggregator.assert_metric(
        CHECK_NAME + '.renamed.metric1',
        tags=['node:host1', 'flavor:test', 'matched_label:foobar'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_metric(
        CHECK_NAME + '.metric2',
        tags=['timestamp:123', 'node:host2', 'matched_label:foobar'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_all_metrics_covered()


def test_openmetrics_mixed_instance(aggregator):
    c = OpenMetricsCheck(CHECK_NAME, None, {}, [], default_instances={
        'foobar': {
            'prometheus_url': 'http://localhost:10249/metrics',
            'namespace': 'foobar',
            'metrics': [
                'metric3',
                'metric4'
            ]
        }, 'openmetrics': {
            'prometheus_url': 'http://localhost:10249/metrics',
            'namespace': 'openmetrics',
            'metrics': [
                'metric2'
            ],
            'label_joins': {
                'metric2': {
                    'label_to_match': 'matched_label',
                    'labels_to_get': ['timestamp']
                },
            },
            'tags': ['extra:bar']
        }},
        default_namespace='openmetrics')
    # run the check twice for label joins
    for _ in range(2):
        c.check({
            'prometheus_url': 'http://custom:1337/metrics',
            'namespace': 'openmetrics',
            'metrics': [
                {'metric1': 'renamed.metric1'}
            ],
            'label_joins': {
                'renamed.metric1': {
                    'label_to_match': 'matched_label',
                    'labels_to_get': ['flavor']
                },
            },
            'label_to_hostname': 'node',
            'tags': ['extra:foo']
        })

    aggregator.assert_metric(
        CHECK_NAME + '.renamed.metric1',
        hostname='host1',
        tags=['node:host1', 'flavor:test', 'matched_label:foobar', 'extra:foo'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_metric(
        CHECK_NAME + '.metric2',
        hostname='host2',
        tags=['timestamp:123', 'node:host2', 'matched_label:foobar', 'extra:foo'],
        metric_type=aggregator.GAUGE
    )
    aggregator.assert_all_metrics_covered()
