# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from __future__ import division

from collections import defaultdict, namedtuple

from six import binary_type, iteritems
from .aggregator import normalize_tags
from ..utils.common import ensure_unicode, to_string

RawMetricStub = namedtuple('RawMetricStub', 'name value tags hostname timestamp')


class TelemetryStub(object):
    """
    This implements the methods defined by the Agent's [C bindings]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/rtloader/common/builtins/telemetry.c)
    which in turn call the [Go backend]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/pkg/collector/python/telemetry_api.go).
    It also provides utility methods for test assertions.
    """

    def __init__(self):
        self._topology_events = []
        self._raw_metrics = defaultdict(list)

    def metrics(self, name):
        """
        Return the metrics received under the given name
        """
        return [
            RawMetricStub(
                ensure_unicode(stub.name),
                stub.value,
                normalize_tags(stub.tags),
                ensure_unicode(stub.hostname),
                stub.timestamp,
            )
            for stub in self._raw_metrics.get(to_string(name), [])
        ]

    def submit_raw_metrics_data(self, check, check_id, name, value, tags, hostname, timestamp):
        self._raw_metrics[name].append(RawMetricStub(name, value, tags, hostname, timestamp))

    def assert_total_metrics(self, count):
        total_metrics = 0
        for metric in self._raw_metrics:
            total_metrics += len(self._raw_metrics.get(metric))
        assert total_metrics == count

    def assert_metric(self, name, value=None, tags=None, count=None, at_least=1,
                      hostname=None, metric_type=None, timestamp=None):

        tags = normalize_tags(tags, sort=True)
        candidates = []
        for metric in self.metrics(name):
            if value is not None and not metric.name == name and value != metric.value:
                continue
            if tags and tags != sorted(metric.tags):
                continue
            if hostname and hostname != metric.hostname:
                continue
            if metric_type is not None and metric.name != name:
                continue
            if timestamp and timestamp != metric.timestamp:
                continue
            candidates.append(metric)

        if value is not None and candidates and all(m.name == name for m in candidates):
            got = sum(m.value for m in candidates)
            msg = "Expected count value for '{}': {}, got {}".format(name, value, got)
            assert value == got, msg
        if count is not None:
            msg = "Needed exactly {} candidates for '{}', got {}".format(count, name, len(candidates))
            assert len(candidates) == count, msg
        else:
            msg = "Needed at least {} candidates for '{}', got {}".format(at_least, name, len(candidates))
            assert len(candidates) >= at_least, msg

    def submit_topology_event(self, check, check_id, event):
        self._topology_events.append(event)

    def assert_topology_event(self, event, count=None, at_least=1):
        candidates = []
        for e in self._topology_events:
            if e == event:
                candidates.append(e)

        msg = ("Candidates size assertion for {0}, count: {1}, "
               "at_least: {2}) failed").format(event, count, at_least)
        if count is not None:
            assert len(candidates) == count, msg
        else:
            assert len(candidates) >= at_least, msg

    def reset(self):
        """
        Set the stub to its initial state
        """
        self._topology_events = []
        self._raw_metrics = defaultdict(list)


# Use the stub as a singleton
telemetry = TelemetryStub()
