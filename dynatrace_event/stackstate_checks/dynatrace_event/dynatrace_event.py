# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os
import time
from datetime import datetime, timedelta

import yaml
from requests import Session
from requests.exceptions import Timeout
from schematics import Model
from schematics.types import StringType, IntType, ListType, DateTimeType, DictType, URLType, BooleanType, ModelType

from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance

try:
    import cPickle as pickle
except ImportError:
    # python 3 support as pickle module
    import pickle

# DYNATRACE_STATE_FILE = "/etc/stackstate-agent/conf.d/dynatrace_event.d/dynatrace_event_state.pickle"
DYNATRACE_STATE_FILE = "/Users/hruhek/PycharmProjects/StackState/stackstate-agent-integrations/dynatrace_event/dynatrace_event_state.pickle"

VERIFY_HTTPS = True
EVENTS_BOOSTRAP_DAYS_DEFAULT = 5
EVENTS_PROCESS_LIMIT_DEFAULT = 10000


class DynatraceEvent(Model):
    eventId = IntType()
    startTime = IntType()
    endTime = IntType()
    entityId = StringType()
    entityName = StringType()
    severityLevel = StringType()
    impactLevel = StringType()
    eventType = StringType()
    eventStatus = StringType()
    tags = ListType(StringType)
    id = StringType()
    source = StringType()


class State(Model):
    latest_sys_updated_on = DateTimeType(required=True)
    change_requests = DictType(StringType, default={})


class InstanceInfo(Model):
    url = URLType(required=True)
    token = StringType(required=True)
    instance_tags = ListType(StringType, default=[])
    events_boostrap_days = IntType(default=EVENTS_BOOSTRAP_DAYS_DEFAULT)
    events_process_limit = IntType(default=EVENTS_PROCESS_LIMIT_DEFAULT)
    verify = BooleanType(default=VERIFY_HTTPS)
    cert = StringType(default='')
    keyfile = StringType(default='')
    state = ModelType(State)


class DynatraceEventCheck(AgentCheck):
    INSTANCE_TYPE = "dynatrace_event"
    SERVICE_CHECK_NAME = "dynatrace_event"

    def __init__(self, name, init_config, instances=None):
        AgentCheck.__init__(self, name, init_config, instances)
        self.url = None
        self.token = None
        self.tags = None
        self.events_boostrap_days = None
        self.events_process_limit = None
        self.state = None
        self.verify = None
        self.cert = None
        self.keyfile = None

    def load_state(self):
        """
        Load the state from memory on each run if any events processed and stored
        otherwise state will be empty
        """
        self.state = DynatraceEventState.load_latest_state()
        if self.state is None:
            self.state = DynatraceEventState()

    def get_instance_key(self, instance):
        if 'url' not in instance:
            raise ConfigurationError('Missing API url in configuration.')

        return TopologyInstance(self.INSTANCE_TYPE, instance["url"])

    def check(self, instance):
        """
        Integration logic
        """
        if 'url' not in instance:
            raise ConfigurationError('Missing API user in configuration.')
        if 'token' not in instance:
            raise ConfigurationError('Missing API Token in configuration.')

        self.url = instance.get('url')
        self.token = instance.get('token')
        self.events_boostrap_days = instance.get('events_boostrap_days', 5)
        self.events_process_limit = instance.get('events_process_limit', 10000)
        self.tags = instance.get('tags', [])
        self.verify = instance.get('verify', True)
        self.cert = instance.get('cert', '')
        self.keyfile = instance.get('keyfile', '')
        self.load_state()
        self.log.debug("After loading the state: {}".format(self.state.data))

        try:
            self.process_events()
            msg = "Dynatrace events processed successfully"
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=self.tags, message=msg)
        except EventLimitReachedException as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags, message=str(e))
            self.load_state()
            # for each entity in the old state send a CLEAR event and remove the instance from state
            # TODO do we need this anymore?
            # self.clear_state_and_send_clear_events()
            self.state.persist()
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags, message=str(e))

    def process_events(self):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        # self.send_filtered_events(events)
        for event in self.collect_events():
            self.new_create_event(event)
        self.log.debug("Persisting the data...")
        self.state.persist()
        self.log.debug("Data in memory is: {}".format(self.state.data))

    def get_events(self, from_time=None, cursor=None):
        """
        Get events from Dynatrace Event API endpoint
        :param from_time: timestamp from which to collect events
        :param cursor:
        :return: Event API endpoint response
        """
        params = ''
        if from_time:
            params = "?from={0}".format(from_time)
        if cursor:
            params = "?cursor={}".format(cursor)
        endpoint = self.url + "/api/v1/events{}".format(params)
        events = self.get_dynatrace_event_json_response(endpoint)
        return events

    def collect_events(self):
        """
        Checks for EventLimitReachedException and process each event API response for next cursor
        until is None or it reach events_process_limit
        """
        from_time = self.state.data.get(self.url, {}).get("lastProcessedEventTimestamp")
        if not from_time:
            from_time = int((datetime.now() - timedelta(days=self.events_boostrap_days)).strftime('%s')) * 1000
        events_response = self.get_events(from_time=from_time)
        if self.event_limit_exceeded_condition(events_response):
            raise EventLimitReachedException("Maximum event limit to process is {} but received total {} events".
                                             format(self.events_process_limit, events_response.get("totalEventCount")))
        events = []
        events_processed = 0
        while events_response:
            for event in events_response.get('events', []):
                dynatrace_event = DynatraceEvent(event)
                dynatrace_event.validate()
                events.append(dynatrace_event)
            events_processed += len(events_response)
            if events_response.get("nextCursor") and events_processed < self.events_process_limit:
                events_response = self.get_events(cursor=events_response.get("nextCursor"))
            else:
                # TODO write lastProcessedEventTimestamp to state
                # self.state.data[self.url]["lastProcessedEventTimestamp"] = events_response.get("to")
                events_response = None
        return events

    def event_limit_exceeded_condition(self, events_response):
        """
        Check if number of events between subsequent check runs exceed the `events_process_limit`
        :return: boolean True or False
        """
        total_event_count = events_response.get("totalEventCount")
        # if events processed last time and total event count exceeded the limit
        if self.state.data.get(self.url, {}).get("lastProcessedEventTimestamp") is not None and \
                total_event_count >= self.events_process_limit:
            return True

    def new_create_event(self, dynatrace_event):
        """
        Create an standard or custom event based on the Dynatrace Severity level
        """
        event = {
            "timestamp": int(time.time()),
            "source_type_name": "Dynatrace Events",
            "msg_title": dynatrace_event.eventType + " on " + dynatrace_event.entityName,
            "msg_text": dynatrace_event.eventType + " on " + dynatrace_event.entityName,
            "tags": [
                "entityId:{0}".format(dynatrace_event.entityId),
                "severityLevel:{0}".format(dynatrace_event.severityLevel),
                "eventType:{0}".format(dynatrace_event.eventType),
                "impactLevel:{0}".format(dynatrace_event.impactLevel),
                "eventStatus:{0}".format(dynatrace_event.eventStatus),
            ]
        }

        # Events with a info severity (6) are send as custom events
        if dynatrace_event.severityLevel == 6:
            event["context"] = {
                "source_identifier": "source_identifier_value",
                "element_identifiers": ["urn:external-id-pattern"],
                "source": "source",
                "category": "category",
                "data": dynatrace_event,
                "source_links": [
                    {"title": "my_event_external_link", "url": "link-to-dynatrace"}
                ]
            }

        self.event(event)

    @staticmethod
    def _current_time_seconds():
        """
        This method is mocked for testing. Do not change its behavior
        :return: current timestamp
        """
        return int(time.time())

    def get_dynatrace_event_json_response(self, endpoint, timeout=10):
        headers = {"Authorization": "Api-Token {}".format(self.token)}
        resp = None
        msg = None
        try:
            with Session() as session:
                session.headers.update(headers)
                session.verify = self.verify
                if self.cert:
                    session.cert = (self.cert, self.keyfile)
                resp = session.get(endpoint)
                if resp.status_code != 200:
                    raise Exception("Got %s when hitting %s" % (resp.status_code, endpoint))
                return yaml.safe_load(resp.text)
        except Timeout:
            msg = "{} seconds timeout when hitting {}".format(timeout, endpoint)
            raise Exception("Exception occured for endpoint {0} with message: {1}".format(endpoint, msg))


class EventLimitReachedException(Exception):
    """
    Exception raised when maximum number of event reached
    """
    pass


class DynatraceEventState(object):
    """
    A class to keep the state of the events coming from Dynatrace. The structure of state looks like below:

    # timestamp   : last event processed timestamp
    # entityId    : EntityId of Dynatrace for which event occured
    # event_type  : Event Type of an event for the EntityId
    # event       : Event details for the EntityId

    state = {
                "url": {
                        "lastProcessedEventTimestamp": timestamp,
                        "events": {
                                    "entityId": {
                                                    "event_type": event
                                                }
                                  }
                        }
            }

    """

    def __init__(self):
        self.data = dict()

    def persist(self):
        try:
            print("Persisting status to %s" % DYNATRACE_STATE_FILE)
            f = open(DYNATRACE_STATE_FILE, 'wb+')
            try:
                pickle.dump(self, f)
            finally:
                f.close()
        except Exception as e:
            print("Error persisting the data: {}".format(str(e)))
            raise e

    def clear(self, instance):
        """
        Clear the instance state as it can have multiple instance state
        :param instance: the instance for which state need to be cleared
        :return: None
        """
        if instance in self.data:
            del self.data[instance]
        else:
            print("There is no state existing for the instance {}".format(instance))

    @classmethod
    def load_latest_state(cls):
        try:
            if not os.path.exists(DYNATRACE_STATE_FILE):
                return None
            f = open(DYNATRACE_STATE_FILE, 'rb')
            try:
                r = pickle.load(f)
                return r
            except Exception as e:
                print("Error loading the state : {}".format(str(e)))
            finally:
                f.close()
        except (IOError, EOFError) as e:
            raise e
