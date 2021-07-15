# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from __future__ import division

from collections import defaultdict, namedtuple

from six import binary_type, iteritems

from ..utils.common import ensure_unicode, to_string

import json


def snapshot(stream):
    return {"start_snapshot": None, "stop_snapshot": None, "stream": stream, "check_states": []}


class HealthStub(object):
    """
    Mainly used for unit testing checks, this stub makes possible to execute
    a check without a running Agent.
    """

    def __init__(self):
        self._snapshots = {}

    def _stream_id(self, check_id, stream):
        return check_id + json.dumps(stream)

    def _ensure_stream(self, check_id, stream):
        stream_id = self._stream_id(check_id, stream)
        if stream_id not in self._snapshots:
            self._snapshots[stream_id] = snapshot(stream)
        return self._snapshots[stream_id]

    def submit_health_check_data(self, check, check_id, stream, data):
        self._ensure_stream(check_id, stream)["check_states"].append(data)

    def submit_health_start_snapshot(self, check, check_id, stream, expiry_seconds, repeat_interval_seconds):
        self._ensure_stream(check_id, stream)["start_snapshot"] = {"expiry_interval_s": expiry_seconds,
                                                                   "repeat_interval_s": repeat_interval_seconds
                                                                   }

    def submit_health_stop_snapshot(self, check, check_id, stream):
        self._ensure_stream(check_id, stream)["stop_snapshot"] = {}

    def get_snapshot(self, check_id, stream):
        return self._snapshots[self._stream_id(check_id, stream)]

    def assert_snapshot(self, check_id, stream,
                        start_snapshot=None, stop_snapshot=None, check_states=[]):
        assert self.get_snapshot(check_id, stream.to_dict()) == {
            "start_snapshot": start_snapshot,
            "stop_snapshot": stop_snapshot,
            "stream": stream.to_dict(),
            "check_states": check_states
        }

    def reset(self):
        self._snapshots = {}


# Use the stub as a singleton
health = HealthStub()
