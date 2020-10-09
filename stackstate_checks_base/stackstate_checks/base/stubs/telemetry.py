# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from __future__ import division

from collections import defaultdict, namedtuple

from six import binary_type, iteritems

from ..utils.common import ensure_unicode, to_string


class TelemetryStub(object):
    """
    Mainly used for unit testing checks, this stub makes possible to execute
    a check without a running Agent.
    """

    def __init__(self):
        self._topology_events = []

    def submit_topology_event(self, check, check_id, event):
        self._topology_events.append(event)

    def assert_topology_event(self, event, count=None, at_least=1):
        candidates = []
        for e in self._topology_events:
            print(e)
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
