# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from __future__ import division

from collections import defaultdict, namedtuple

from six import binary_type, iteritems

from ..utils.common import ensure_unicode, to_string


def component(id, type, data):
    return {"id": id, "type": type, "data": data}


def relation(source_id, target_id, type, data):
    return {"source_id": source_id, "target_id": target_id, "type": type, "data": data}


def snapshot(instance_key):
    return {"start_snapshot": False, "stop_snapshot": False,
            "instance_key": instance_key, "components": [], "relations": []}


class TopologyStub(object):
    """
    Mainly used for unit testing checks, this stub makes possible to execute
    a check without a running Agent.
    """

    def __init__(self):
        self._snapshots = {}

    def _ensure_instance(self, check_id, instance_key):
        if check_id not in self._snapshots:
            self._snapshots[check_id] = snapshot(instance_key)
        return self._snapshots[check_id]

    def submit_component(self, check, check_id, instance_key, id, type, data):
        self._ensure_instance(check_id, instance_key)["components"].append(component(id, type, data))

    def submit_relation(self, check, check_id, instance_key, source_id, target_id, type, data):
        self._ensure_instance(check_id, instance_key)["relations"].append(relation(source_id, target_id, type, data))

    def submit_start_snapshot(self, check, check_id, instance_key):
        self._ensure_instance(check_id, instance_key)["start_snapshot"] = True

    def submit_stop_snapshot(self, check, check_id, instance_key):
        self._ensure_instance(check_id, instance_key)["stop_snapshot"] = True

    def get_snapshot(self, check_id):
        return self._snapshots[check_id]

    def assert_snapshot(self, check_id, instance_key,
                        start_snapshot=False, stop_snapshot=False, components=[], relations=[]):
        assert self.get_snapshot(check_id) == {
            "start_snapshot": start_snapshot,
            "stop_snapshot": stop_snapshot,
            "instance_key": instance_key,
            "components": components,
            "relations": relations
        }

    def reset(self):
        self._snapshots = {}


# Use the stub as a singleton
topology = TopologyStub()
