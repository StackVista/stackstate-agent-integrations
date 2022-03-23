# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from __future__ import division

from functools import reduce


def component(id, type, data):
    return {"id": id, "type": type, "data": data}


def relation(source_id, target_id, type, data):
    return {"source_id": source_id, "target_id": target_id, "type": type, "data": data}


def delete(identifier):
    return identifier


def snapshot(instance_key):
    return {"start_snapshot": False, "stop_snapshot": False,
            "instance_key": instance_key, "components": [], "relations": [], "delete_ids": []}


def get_relation_id(relation):
    return relation.get('source_id', '') + ' <- (' + relation.get('type', '') + \
        ') -> ' + relation.get('target_id', '')


class TopologyStub(object):
    """
    Mainly used for unit testing checks, this stub makes possible to execute
    a check without a running Agent.
    """

    def __init__(self):
        self._snapshots = {}
        self._components_checked = {}
        self._relations_checked = {}
        self._delete_ids_checked = {}

    def _ensure_instance(self, check_id, instance_key):
        if check_id not in self._snapshots:
            self._snapshots[check_id] = snapshot(instance_key)
        return self._snapshots[check_id]

    def submit_component(self, check, check_id, instance_key, id, type, data):
        self._ensure_instance(check_id, instance_key)["components"].append(component(id, type, data))

    def submit_delete(self, check, check_id, instance_key, identifier):
        self._ensure_instance(check_id, instance_key)["delete_ids"].append(delete(identifier))

    def submit_relation(self, check, check_id, instance_key, source_id, target_id, type, data):
        self._ensure_instance(check_id, instance_key)["relations"].append(relation(source_id, target_id, type, data))

    def submit_start_snapshot(self, check, check_id, instance_key):
        self._ensure_instance(check_id, instance_key)["start_snapshot"] = True

    def submit_stop_snapshot(self, check, check_id, instance_key):
        self._ensure_instance(check_id, instance_key)["stop_snapshot"] = True

    def get_snapshot(self, check_id):
        return self._snapshots[check_id]

    def assert_snapshot(self, check_id, instance_key,
                        start_snapshot=False, stop_snapshot=False, components=None, relations=None, delete_ids=None):
        if relations is None:
            relations = []
        if components is None:
            components = []
        if delete_ids is None:
            delete_ids = []
        assert self.get_snapshot(check_id) == {
            "start_snapshot": start_snapshot,
            "stop_snapshot": stop_snapshot,
            "instance_key": instance_key.to_dict(),
            "components": components,
            "relations": relations,
            "delete_ids": delete_ids
        }

    def reset(self):
        self._snapshots = {}
        self._components_checked = {}
        self._relations_checked = {}
        self._delete_ids_checked = {}

    def assert_component(self, components, id, type, checks=None):
        if checks is None:
            checks = {}
        msg = []
        comp = None
        for component in components:
            if component["id"] == id and component["type"] == type:
                comp = component
                break
        if comp is None:
            msg.append("Component not found id={} type={}".format(id, type))
            msg.append("Components the were found:")
            for component in components:
                msg.append("- {} ({})".format(component.get("id"), component.get("type")))
            assert False, '\n'.join(msg)
        self._components_checked[id] = True
        self.assert_data(checks, comp, msg)
        return comp

    @staticmethod
    def assert_data(checks, topology_element, msg):
        """
        Asserts if component or data dictionary has correct values.
        :param checks: checks collection
        :param topology_element: component or relation to assert
        :param msg: for appending error messages
        """
        for key in checks:
            try:
                value = reduce(dict.__getitem__, ('data.' + key).split('.'), topology_element)
                if value != checks[key]:
                    msg.append('data {}: {} != {}'.format(key, value, checks[key]))
            except Exception as e:
                msg.append('data {}: error {}'.format(key, e))
        if msg:
            assert False, '\n'.join(msg)

    def assert_relation(self, relations, source_id, target_id, type, checks=None):
        if checks is None:
            checks = {}
        msg = []
        rel = None
        for relation in relations:
            if relation["source_id"] == source_id and relation["target_id"] == target_id and \
                    relation["type"] == type:
                rel = relation
                break
        if rel is None:
            msg.append("Relation not found source_id={} type={} target_id={}".format(source_id, type, target_id))
            msg.append("Relations that were found:")
            for relation in relations:
                msg.append("- {} <- ({}) -> {}".format(
                    relation.get("source_id"),
                    relation.get("type"),
                    relation.get("target_id"))
                )
            assert False, '\n'.join(msg)
        self._relations_checked[get_relation_id(rel)] = True
        self.assert_data(checks, rel, msg)
        return rel

    def assert_all_checked(self, components, relations, unchecked_relations=0, unchecked_components=0):
        msg = []
        if len(self._components_checked.keys()) + unchecked_components < len(components):
            msg.append("The following {} components were left unchecked:".format(
                len(components) - len(self._components_checked.keys())
            ))
            for component in components:
                if component["id"] not in self._components_checked:
                    msg.append("- {} ({})".format(component.get("id"), component.get("type")))
            for component in components:
                print(component["id"])
        elif len(self._components_checked.keys()) + unchecked_components > len(components):
            msg.append("More components are checked than there were there.")
        if len(self._relations_checked.keys()) + unchecked_relations < len(relations):
            msg.append("The following {} relations were left unchecked:".format(
                len(relations) - len(self._relations_checked.keys())
            ))
            for relation in relations:
                rid = get_relation_id(relation)
                if rid not in self._relations_checked:
                    msg.append("- {} <- ({}) -> {}".format(
                        relation.get("source_id"), relation.get("type"), relation.get("target_id"))
                    )
        elif len(self._relations_checked.keys()) + unchecked_relations > len(relations):
            msg.append("More relations are checked than there were there.")
        if msg:
            assert False, '\n'.join(msg)


# Use the stub as a singleton
topology = TopologyStub()
