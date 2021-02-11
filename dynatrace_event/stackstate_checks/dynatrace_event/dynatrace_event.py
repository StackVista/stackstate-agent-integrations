# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance

import requests
from requests import Session
import yaml
from datetime import datetime, timedelta
import time
import json

import os

try:
    import cPickle as pickle
except ImportError:
    # python 3 support as pickle module
    import pickle

# DYNATRACE_STATE_FILE = "/etc/stackstate-agent/conf.d/dynatrace_event.d/dynatrace_event_state.pickle"
DYNATRACE_STATE_FILE = "/Users/hruhek/PycharmProjects/StackState/stackstate-agent-integrations/dynatrace_event/dynatrace_event_state.pickle"


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
            self.clear_state_and_send_clear_events()
            self.state.persist()
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags, message=str(e))

    def process_events(self):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        touched_entities = self.collect_events()
        self.send_filtered_events(touched_entities)
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
        touched_entities = []
        events_processed = 0
        while events_response:
            entities, events_processed = self.process_events_response(events_response, events_processed)
            touched_entities.extend(entities)
            next_cursor = events_response.get("nextCursor")
            if next_cursor and events_processed < self.events_process_limit:
                events_response = self.get_events(cursor=next_cursor)
            else:
                self.state.data[self.url]["lastProcessedEventTimestamp"] = events_response.get("to")
                events_response = None
        return list(set(touched_entities))

    def process_events_response(self, events_response, events_processed):
        touched_entities = []
        if "error" in events_response:
            raise Exception("Error in pulling the events : {}".format(events_response.get("error").get("message")))
        for item in events_response["events"]:
            # if the limit reached for event_process_limit then stop processing and break from loop
            if events_processed >= self.events_process_limit:
                self.log.debug("Events Process Limit reached : {}".format(events_processed))
                break
            entity_id = item.get("entityId")
            current_event_status = item.get("eventStatus")
            start_time = int(item.get("startTime"))
            event_type = item.get("eventType")
            state_events = self.state.data.get(self.url, {}).get("events", {})

            # when the check runs first time or after the reset
            if self.url not in self.state.data:
                self.state.data[self.url] = {}
                self.state.data[self.url]["events"] = {}

            entity_events = state_events.get(entity_id, {})
            event = entity_events.get(event_type)
            end_time = entity_events.get(event_type, {}).get("endTime")
            old_event_status = entity_events.get(event_type, {}).get("eventStatus")
            # either closed or open events come, keep in state to compare in the past response
            # if we have to remove this event type or need to keep it
            if event is None:
                self.state.data[self.url]["events"][entity_id] = {event_type: item}
                touched_entities.append(entity_id)
            # new event for same event type in entityId with latest time
            elif start_time > end_time and old_event_status == current_event_status:
                self.state.data[self.url]["events"][entity_id][event_type] = item
                touched_entities.append(entity_id)
            # new event with CLOSED status come in for existing OPEN event for an even type of that entityId
            elif old_event_status == "CLOSED" and current_event_status == "OPEN":
                del self.state.data[self.url]["events"][entity_id][event_type]
                touched_entities.append(entity_id)
            events_processed += 1
        return touched_entities, events_processed

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

    def send_filtered_events(self, touched_entities):
        """
        Method to filter the closed events and create the health event for open and cleared events
        """
        events = self.state.data.get(self.url).get("events")
        # process only those touched entities from state
        for entityId in touched_entities:
            open_events = []
            # check from state for that entityID and evaluate again
            event_type_values = events.get(entityId)
            # if we have open events for an entityId then create event with the health check
            if event_type_values:
                # in Python 3.x because keys returns an iterator instead of a list. so to support both versions
                # create a list of keys
                for event_type in list(event_type_values):
                    event_status = event_type_values.get(event_type).get("eventStatus")
                    if event_status == "CLOSED":
                        del self.state.data[self.url]["events"][entityId][event_type]
                    else:
                        self.log.debug("Appending an open event for entityID {}: {}".format
                                       (entityId, event_type_values[event_type]))
                        open_events.append(event_type_values[event_type])
                # since there are no open events, it means we processed everything
                # then delete the empty entityId from state
                if len(open_events) == 0:
                    del self.state.data[self.url]["events"][entityId]
                else:
                    # create the health event for open_events and if open_events
                    # are empty then create CLEAR health state
                    self.create_health_event(entityId, open_events)
            else:
                # the case could be we closed the event in `process_events_response` and now entityID is empty then
                # we send the clear health for that entityId and delete the empty entityId from state
                self.create_health_event(entityId, [])
                del self.state.data[self.url]["events"][entityId]

    def clear_state_and_send_clear_events(self):
        """
        Method to send CLEAR health state for all existing open entity and clear the state for the instance
        """
        events = self.state.data.get(self.url).get("events")
        for entityId in events.keys():
            health_state = "CLEAR"
            detailed_msg = ""
            self.create_event(entityId, health_state, detailed_msg)
        self.log.info("Clear state for {} entities sent".format(len(events.keys())))
        self.state.clear(self.url)

    def create_health_event(self, entity_id, open_events):
        """
        Process each severity level of the events for an entityId and create the event with highest health state
        :param entityId: EntityId for which different events are considered
        :param open_events: Open events with different severity level for an EntityId
        """
        # TODO document this
        health_states = {"UNKNOWN": 0, "CLEAR": 1, "DEVIATING": 2, "CRITICAL": 3}
        severity_level = {"AVAILABILITY": "CRITICAL", "CUSTOM_ALERT": "CRITICAL", "PERFORMANCE": "DEVIATING",
                          "RESOURCE_CONTENTION": "DEVIATING", "ERROR": "CRITICAL",
                          "MONITORING_UNAVAILABLE": "DEVIATING"}
        health_state = "UNKNOWN"
        detailed_msg = """|  EventType  |  SeverityLevel  |  Impact  |  Open Since  |  Tags  |  Source  |\n
        |-------------|-----------------|----------|--------------|--------|----------|\n
        """
        if open_events:
            for events in open_events:
                severity = events.get("severityLevel")
                impact = events.get("impactLevel")
                event_type = events.get("eventType")
                event_health_state = severity_level.get(severity)
                if not event_health_state:
                    self.log.warning("Unknown severity level encountered: {}".format(severity))
                    event_health_state = "UNKNOWN"
                open_since = (datetime.fromtimestamp(events.get("startTime")/1000)).strftime("%b %-d, %Y, %H:%M:%S")
                tags = json.dumps(events.get("tags"), sort_keys=True)
                events_source = "dynatrace-"+events.get("source")
                detailed_msg += "|  {0}  |  {1}  |  {2}  |  {3}  |  {4}  |  {5}  |\n" \
                                "".format(event_type, severity, impact, open_since, tags, events_source)
                if health_states.get(event_health_state) > health_states.get(health_state):
                    health_state = event_health_state
            self.log.debug("Logging an event for entity {0} with health: {1}".format(entity_id, health_state))
            self.create_event(entity_id, health_state, detailed_msg)
        else:
            self.create_event(entity_id, health_state="OK", detailed_msg="")

    def create_event(self, entity_id, health_state, detailed_msg):
        """
        Create an event based on the data coming in from entity_event
        """
        tags = [
            "entityId:{0}".format(entity_id),
            "health:{0}".format(health_state)
        ]
        self.event({
            "timestamp": self._current_time_seconds(),
            "source_type_name": "Dynatrace Events",
            "msg_title": "",
            "msg_text": detailed_msg,
            "tags": tags
        })

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
        except requests.exceptions.Timeout:
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
