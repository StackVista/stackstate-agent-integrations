# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from __future__ import division

from collections import defaultdict, namedtuple

from six import binary_type, iteritems

from ..utils.common import ensure_unicode, to_string


def normalize_tags(tags, sort=False):
    # The base class ensures the Agent receives bytes, so to avoid
    # prefacing our asserted tags like b'foo:bar' we'll convert back.
    if tags:
        if sort:
            return sorted(ensure_unicode(tag) for tag in tags)
        else:
            return [ensure_unicode(tag) for tag in tags]
    return tags


class TelemetryStub(object):
    """
    Mainly used for unit testing checks, this stub makes possible to execute
    a check without a running Agent.
    """

    def __init__(self):
        self._topology_events = []

    def submit_topology_event(self, check, check_id, event):
        self._topology_events.append(event)

    # Potential kwargs: aggregation_key, alert_type, event_type,
    # msg_title, source_type_name
    def assert_topology_event(self, msg_text, count=None, at_least=1, exact_match=True,
                     tags=None, **kwargs):
        candidates = []
        for e in self._topology_events:
            if exact_match and msg_text != e['msg_text'] or \
                    msg_text not in e['msg_text']:
                continue
            if tags and set(tags) != set(e['tags']):
                continue
            for name, value in iteritems(kwargs):
                if e[name] != value:
                    break
            else:
                candidates.append(e)

        msg = ("Candidates size assertion for {0}, count: {1}, "
               "at_least: {2}) failed").format(msg_text, count, at_least)
        if count is not None:
            assert len(candidates) == count, msg
        else:
            assert len(candidates) >= at_least, msg


# Use the stub as a singleton
telemetry = TelemetryStub()
