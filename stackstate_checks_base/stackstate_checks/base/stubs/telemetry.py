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
    Mainly used for unit testing checks, this stub makes possible to execute
    a check without a running Agent.
    """

    def __init__(self):
        self._topology_events = []
        self._raw_metrics = defaultdict(list)

    def raw_metrics(self, name):
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

    def assert_raw_metrics_data(self, check, check_id, name, value, tags, hostname, timestamp):
        tags = normalize_tags(tags, sort=True)

        candidates = []
        for raw_metric in self.raw_metrics(name):
            if value is not None and value != raw_metric.value:
                continue

            if tags and tags != sorted(raw_metric.tags):
                continue

            if hostname and hostname != raw_metric.hostname:
                continue

            if timestamp and timestamp != raw_metric.timestamp:
                continue

            candidates.append(raw_metric)

        if value is not None and candidates:
            got = sum(m.value for m in candidates)
            msg = "Expected count value for '{}': {}, got {}".format(name, value, got)
            assert value == got, msg

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


# Use the stub as a singleton
telemetry = TelemetryStub()
