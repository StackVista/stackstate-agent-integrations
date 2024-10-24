# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base import AgentCheck, ConfigurationError, StackPackInstance
from stackstate_checks.base.errors import CheckException

"""
    StackState.
    Zabbix host topology and problem integration

    Current limitations:
    - Unsupported Zabbix Problem acks
    - Unsupported Zabbix version 4+ severity upgrades, currently the trigger's severity is used for compatibility
"""

import requests
import time
import json

from stackstate_checks.utils.identifiers import Identifiers


class ZabbixHost:
    def __init__(self, host_id, host, name, host_groups, tags):
        assert(type(host_groups == list))
        self.host_id = host_id
        self.host = host
        self.name = name
        self.host_groups = host_groups
        self.tags = tags

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "ZabbixHost(host_id:%s, host:%s, name:%s, host_groups:%s.)" % (self.host_id, self.host, self.name,
                                                                              self.host_groups)


class ZabbixHostGroup:
    def __init__(self, host_group_id, name):
        self.host_group_id = host_group_id
        self.name = name

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "ZabbixHostGroup(host_group_id:%s, name:%s.)" % (self.host_group_id, self.name)


class ZabbixTrigger:
    def __init__(self, trigger_id, description, priority):
        self.trigger_id = trigger_id
        self.description = description
        self.priority = priority  # translates to severity

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "ZabbixTrigger(trigger_id:%s, description:%s, priority:%s.)" % (self.trigger_id, self.description,
                                                                               self.priority)


class ZabbixEvent:
    def __init__(self, event_id, acknowledged, host_ids, trigger):
        self.event_id = event_id
        self.acknowledged = acknowledged  # 0/1 (not) acknowledged
        self.host_ids = host_ids
        self.trigger = trigger  # ZabbixTrigger

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "ZabbixEvent(event_id:%s, acknowledged:%s, host_ids:%s, trigger:%s)" % (self.event_id, self.acknowledged,
                                                                                       self.host_ids, self.trigger)


class ZabbixProblem:
    def __init__(self, event_id, acknowledged, trigger_id, severity):
        self.event_id = event_id
        self.acknowledged = acknowledged
        self.trigger_id = trigger_id
        self.severity = severity

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "ZabbixProblem(event_id:%s, acknowledged:%s, trigger_id:%s, severity:%s)" % \
               (self.event_id, self.acknowledged, self.trigger_id, self.severity)


class ZabbixCheck(AgentCheck):
    SERVICE_CHECK_NAME = INSTANCE_TYPE = "Zabbix"
    begin_epoch = None  # start to listen to events from epoch timestamp

    def __init__(self, name, init_config, instances=None):
        AgentCheck.__init__(self, name, init_config, instances)
        self.url = None
        self.user = None
        self.password = None

    def get_instance_key(self, instance):
        if 'url' not in instance:
            raise ConfigurationError('Missing API url in configuration.')

        return StackPackInstance(self.INSTANCE_TYPE, instance["url"])

    def check(self, instance):
        """
        Integration logic
        """
        if 'user' not in instance:
            raise ConfigurationError('Missing API user in configuration.')
        if 'password' not in instance:
            raise ConfigurationError('Missing API password in configuration.')

        stackstate_environment = instance.get('stackstate_environment', 'Production')
        self.ssl_verify = instance.get('ssl_verify', True)

        url = instance['url']

        topology_instance = {
            "type": self.SERVICE_CHECK_NAME,
            "url": url
        }
        try:
            self.start_snapshot()
            self.check_connection(url)
            auth = self.login(url, instance['user'], instance['password'])

            hosts = {}  # key: host_id, value: ZabbixHost

            # Topology, get all hosts
            for zabbix_host in self.retrieve_hosts(url, auth):
                self.process_host_topology(topology_instance, zabbix_host, stackstate_environment)

                hosts[zabbix_host.host_id] = zabbix_host

            # Telemetry, get all problems.
            zabbix_problems = self.retrieve_problems(url, auth)

            event_ids = list(problem.event_id for problem in zabbix_problems)
            zabbix_events = [] if len(event_ids) == 0 else self.retrieve_events(url, auth, event_ids)

            rolled_up_events_per_host = {}  # host_id -> [ZabbixEvent]
            most_severe_severity_per_host = {}  # host_id -> severity int
            for zabbix_event in zabbix_events:
                for host_id in zabbix_event.host_ids:
                    if host_id in rolled_up_events_per_host:
                        rolled_up_events_per_host[host_id].append(zabbix_event)
                        if most_severe_severity_per_host[host_id] < zabbix_event.trigger.priority:
                            most_severe_severity_per_host[host_id] = zabbix_event.trigger.priority
                    else:
                        rolled_up_events_per_host[host_id] = [zabbix_event]
                        most_severe_severity_per_host[host_id] = zabbix_event.trigger.priority

            self.log.debug('rolled_up_events_per_host:' + str(rolled_up_events_per_host))
            self.log.debug('most_severe_severity_per_host:' + str(most_severe_severity_per_host))

            # iterate all hosts to send an event per host, either in OK/PROBLEM state
            for host_id, zabbix_host in hosts.items():
                severity = 0
                triggers = []

                if host_id in rolled_up_events_per_host:
                    triggers = [event.trigger.description for event in rolled_up_events_per_host[host_id]]
                    severity = most_severe_severity_per_host[host_id]

                self.event({
                    'timestamp': int(time.time()),
                    'msg_title': "Zabbix event on host '{}': severity: {}".format(zabbix_host.name, severity),
                    'msg_text': "Zabbix event on host '{}': severity: {}".format(zabbix_host.name, severity),
                    'source_type_name': self.INSTANCE_TYPE,
                    'host': self.hostname,
                    'tags': [
                        'host_id:%s' % host_id,
                        'host:%s' % zabbix_host.host,
                        'host_name:%s' % zabbix_host.name,
                        'severity:%s' % severity,
                        'triggers:%s' % triggers
                    ]
                })
            self.stop_snapshot()
            msg = "Zabbix instance detected at %s " % url
            tags = ["url:%s" % url]
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=tags, message=msg)
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e))

    def process_host_topology(self, topology_instance, zabbix_host, stackstate_environment):
        external_id = "urn:host:/%s" % zabbix_host.host
        identifiers = list()
        identifiers.append(Identifiers.create_host_identifier(zabbix_host.host))
        identifiers.append(zabbix_host.host)

        url = topology_instance.get('url')
        if 'http' in url or 'https' in url:
            instance_url = url.split("//")[1].split("/")[0]
        else:
            instance_url = url.split("/")[0]
        labels = ['zabbix', 'instance_url:%s' % instance_url]
        for host_group in zabbix_host.host_groups:
            labels.append('host group:%s' % host_group.name)
        data = {
            'name': zabbix_host.name,
            'host_id': zabbix_host.host_id,
            'host': zabbix_host.host,
            'layer': 'machines',
            # use host group of component as StackState domain when there is only one host group
            'domain': zabbix_host.host_groups[0].name if len(zabbix_host.host_groups) == 1 else 'Zabbix',
            'identifiers': identifiers,
            'environment': stackstate_environment,
            'host_groups': [host_group.name for host_group in zabbix_host.host_groups],
            'labels': labels,
            'tags': zabbix_host.tags,
            'instance': instance_url
        }

        self.component(external_id, "zabbix_host", data=data)

    def retrieve_events(self, url, auth, event_ids):
        assert(type(event_ids) == list)
        self.log.debug("Retrieving events for event_ids: %s." % event_ids)

        params = {
            "object": 0,  # trigger events
            "eventids": event_ids,
            "output": ["eventid", "value", "severity", "acknowledged"],
            "selectHosts": ["hostid"],
            "selectRelatedObject": ["triggerid", "description", "priority"]
        }

        response = self.method_request(url, "event.get", auth=auth, params=params)

        events = response.get('result', [])
        for event in events:
            event_id = event.get('eventid', None)
            acknowledged = event.get('acknowledged', None)

            hosts_items = event.get('hosts', [])
            host_ids = []
            for item in hosts_items:
                host_id = item.get('hostid', None)
                host_ids.append(host_id)

            trigger = event.get('relatedObject', {})
            trigger_id = trigger.get('triggerid', None)
            trigger_description = trigger.get('description', None)
            trigger_priority = trigger.get('priority', None)

            trigger = ZabbixTrigger(trigger_id, trigger_description, trigger_priority)
            zabbix_event = ZabbixEvent(event_id, acknowledged, host_ids, trigger)

            self.log.debug("Parsed ZabbixEvent: %s." % zabbix_event)

            if not trigger_id or not trigger_description or not trigger_priority or not event_id or len(host_ids) == 0:
                self.log.warn("Incomplete ZabbixEvent, got: %s" % zabbix_event)
            if acknowledged == '0':
                yield zabbix_event

    def retrieve_hosts(self, url, auth):
        self.log.debug("Retrieving hosts.")
        params = {
            "output": ["hostid", "host", "name", "maintenance_status"],
            "selectGroups": ["groupid", "name"],
            "selectTags": ["tag", "value"]
        }
        response = self.method_request(url, "host.get", auth=auth, params=params)
        for item in response.get("result", []):
            host_id = item.get("hostid", None)
            host = item.get("host", None)
            name = item.get("name", None)
            raw_groups = item.get('groups', [])
            host_tags = item.get('tags', [])
            maintenance_status = item.get("maintenance_status", "0")
            groups = []
            for raw_group in raw_groups:
                host_group_id = raw_group.get('groupid', None)
                host_group_name = raw_group.get('name', None)
                zabbix_host_group = ZabbixHostGroup(host_group_id, host_group_name)
                groups.append(zabbix_host_group)
            tags = []
            for tag in host_tags:
                tags.append("{}:{}".format(tag.get('tag'), tag.get('value')))
            zabbix_host = ZabbixHost(host_id, host, name, groups, tags)
            if not host_id or not host or not name or len(groups) == 0:
                self.log.warn("Incomplete ZabbixHost, got: %s" % zabbix_host)
            if maintenance_status == "0":
                yield zabbix_host

    def retrieve_problems(self, url, auth):
        self.log.debug("Retrieving problems.")

        params = {
            "object": 0,  # only interested in triggers
            "output": ["severity", "objectid", "acknowledged"]
        }
        response = self.method_request(url, "problem.get", auth=auth, params=params)
        for item in response.get('result', []):
            event_id = item.get("eventid", None)
            acknowledged = item.get("acknowledged", None)
            # Object id is in case of object=0 a trigger.
            trigger_id = item.get("objectid", None)

            # for Zabbix versions <4.0 we need to get the trigger.priority and if priority doesn't exist then
            # either trigger is disabled or doesn't exist
            priority = self.get_trigger_priority(url, auth, trigger_id)
            severity = item.get("severity", priority)

            zabbix_problem = ZabbixProblem(event_id, acknowledged, trigger_id, severity)

            self.log.debug("Parsed ZabbixProblem %s." % zabbix_problem)
            if not event_id or not trigger_id or not severity:
                self.log.warn("Incomplete ZabbixProblem, got: %s" % zabbix_problem)

            if priority is not None:
                # send the problem only in case trigger is enabled and will get the priority always in enabled cases.
                yield zabbix_problem

    def get_trigger_priority(self, url, auth, trigger_id):
        # `monitored` flag make sure we only get enabled triggers
        params = {
            "output": ["priority"],
            "triggerids": [trigger_id],
            "monitored": True
        }
        response = self.method_request(url, "trigger.get", auth=auth, params=params)
        trigger = response.get('result')
        # since result is a list so check if it has trigger object then get priority
        if len(trigger) > 0:
            return trigger[0].get("priority")
        return None

    def check_connection(self, url):
        """
        Check Zabbix connection
        :param url: Zabbix API location
        :return: None
        """
        self.log.debug("Checking connection.")
        try:
            response = self.method_request(url, "apiinfo.version")
            version = response['result']
            self.log.info("Connected to Zabbix version %s." % version)
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK)
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL,
                               message="Failed to connect to Zabbix on url %s. Please refer to Agent's "
                                       "collector.log log file." % url)
            raise e

    def login(self, url, user, password):
        """
        Log in into Zabbix with provided credentials
        :param url: Zabbix API location
        :param user: in configuration provided credentials
        :param password: in configuration provided credentials
        :return: session string to use in subsequent requests
        """
        self.log.debug("Logging in.")
        params = {
            "user": user,
            "password": password
        }
        try:
            response = self.method_request(url, "user.login", params=params)
            return response['result']
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL,
                               message="Failed to log in into Zabbix at %s with provided credentials." % url)
            raise e

    def method_request(self, url, name, auth=None, params={}, request_id=1):
        payload = {
            "jsonrpc": "2.0",
            "method": "%s" % name,
            "id": request_id,
            "params": params
        }
        if auth:
            payload['auth'] = auth

        self.log.debug("Request to URL: %s" % url)
        self.log.debug("Request payload: %s" % payload)
        response = requests.get(url, json=payload, verify=self.ssl_verify)
        response.raise_for_status()
        self.log.debug("Request response: %s" % response.text)
        try:
            response_json = json.loads(response.text.encode('utf-8'))
            return response_json
        except UnicodeEncodeError as e:
            raise CheckException('Encoding error: "%s" in response from url %s' % (e, response.url))
        except Exception as e:
            raise Exception('Error "%s" in response from url %s' % (str(e), response.url))
