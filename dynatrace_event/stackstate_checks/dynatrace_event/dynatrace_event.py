# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance
from .util import DynatraceEventState
from .dynatrace_exception import EventLimitReachedException

import requests
from requests import Session
import yaml
from datetime import datetime, timedelta
import time
import json


class DynatraceEventCheck(AgentCheck):

    INSTANCE_TYPE = "dynatrace_event"
    SERVICE_CHECK_NAME = "dynatrace_event"

    def __init__(self, name, init_config, instances=None):
        AgentCheck.__init__(self, name, init_config, instances)
        self.url = None
        self.token = None
        self.tags = None
        self.environment = None
        self.events_boostrap_days = None
        self.events_process_limit = None
        self.domain = None
        self.state = None
        self.verify = None
        self.cert = None
        self.keyfile = None

    def load_state(self):
        """
        Load the state from memory on each run if any events processed and stored
        otherwise state will be empty
        """
        self.state = DynatraceEventState.load_latest_status()
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
        self.environment = instance.get('environment', 'production')
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
            self.clear_state()
            self.state.persist()
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags, message=str(e))

    def process_events(self):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        self.collect_events()
        self.send_filtered_events()
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
        events = self.get_json_response(endpoint)
        return events

    def collect_events(self):
        """
        Checks for EventLimitReachedException and process each event API response for next cursor
        untill is None or it reach events_process_limit
        """
        from_time = self.state.data.get(self.url)
        if not from_time:
            from_time = int((datetime.now() - timedelta(days=self.events_boostrap_days)).strftime('%s')) * 1000
        events_response = self.get_events(from_time=from_time)
        if self.event_limit_exceeded_condition(events_response):
            raise EventLimitReachedException("Maximum event limit to process is {} but received total {} events".
                                             format(self.events_process_limit, events_response.get("totalEventCount")))
        # touched_entities = []
        events_processed = 0
        while events_response:
            next_cursor = events_response.get("nextCursor")
            events_processed = self.process_events_response(events_response, events_processed)
            # touched_entities.append(events)
            if next_cursor and events_processed < self.events_process_limit:
                events_response = self.get_events(cursor=next_cursor)
            else:
                self.state.data[self.url] = events_response.get("to")
                events_response = None

    def process_events_response(self, events_response, events_processed):
        if "error" in events_response:
            self.log.exception("Error in pulling the events : {}".format(events_response.get("error").get("message")))
            raise Exception("Error in pulling the events : {}".format(events_response.get("error").get("message")))
        for item in events_response["events"]:
            # if the limit reached for event_process_limit then break from loop
            if self.should_stop_processing(events_processed):
                self.log.debug("Events Process Limit reached : {}".format(events_processed))
                break
            entityId = item.get("entityId")
            event_status = item.get("eventStatus")
            start_time = int(item.get("startTime"))
            event_type = item.get("eventType")
            state_events = self.state.data.get(self.url + "/events", {})

            # when the check runs first time or after the reset
            if self.url + "/events" not in self.state.data:
                self.state.data[self.url + "/events"] = {}

            # Create an event when no event exist for that entityId
            entity_events = state_events.get(entityId)
            if entity_events is None:
                self.log.debug("Creating a new event type for an entityId")
                self.state.data[self.url + "/events"][entityId] = {event_type: item}
            # Check if event already exist for that entityId
            else:
                event = entity_events.get(event_type)
                end_time = entity_events.get(event_type, {}).get("endTime")
                status = entity_events.get(event_type, {}).get("eventStatus")
                # different type of event can exist for same entityId
                if event is None and event_status == "OPEN":
                    self.log.debug("Creating a new open event type for an existing entityId")
                    self.state.data[self.url + "/events"][entityId][event_type] = item
                # new event for same entityId with latest time
                elif start_time > end_time and status == event_status:
                    self.log.info("Updating the existing event type for an existing entityId with new event")
                    self.state.data[self.url + "/events"][entityId][event_type] = item
                # new event with CLOSED status come in for existing OPEN event for an even type of that entityId
                elif status == "CLOSED" and event_status == "OPEN":
                    self.log.info("Deleting an existing open event type for an existing entityId ")
                    del self.state.data[self.url + "/events"][entityId][event_type]
            events_processed += 1
        return events_processed

    def event_limit_exceeded_condition(self, events_response):
        """
        Check if number of events between subsequent check runs exceed the `events_process_limit`
        :return: boolean True or False
        """
        total_event_count = events_response.get("totalEventCount")
        # if events processed last time and total event count exceeded the limit
        if self.state.data.get(self.url) is not None and total_event_count > self.events_process_limit:
            return True

    def send_filtered_events(self):
        """
        Method to filter the closed events and create the health event for open and cleared events
        """
        events = self.state.data.get(self.url + "/events")
        if events:
            # in Python 3.x because keys returns an iterator instead of a list. so to support both versions
            # create a list of keys
            for entityId in list(events):
                open_events = []
                event_type_values = events.get(entityId)
                # if we have open events for an entityId then create event with the health check
                if event_type_values:
                    # in Python 3.x because keys returns an iterator instead of a list. so to support both versions
                    # create a list of keys
                    for event_type in list(event_type_values):
                        event_status = event_type_values.get(event_type).get("eventStatus")
                        if event_status == "CLOSED":
                            del self.state.data[self.url + "/events"][entityId][event_type]
                        else:
                            self.log.debug("Appending an open event for entityID {}: {}".format
                                           (entityId, event_type_values[event_type]))
                            open_events.append(event_type_values[event_type])
                    if not self.state.data[self.url + "/events"][entityId]:
                        self.create_event(entityId, healthState="OK", detailedmsg="")
                        del self.state.data[self.url + "/events"][entityId]
                    if len(open_events) > 0:
                        self.create_health_event(entityId, open_events)
                else:
                    # else we send the clear health for that entityId and delete the empty entityId
                    self.create_event(entityId, healthState="OK", detailedmsg="")
                    del self.state.data[self.url + "/events"][entityId]
        self.log.debug("After filtering the closed events :- {}".format(self.state.data))

    def clear_state(self):
        """
        Method to send OK health state for all existing open entity and clear the state for the instance
        """
        events = self.state.data.get(self.url + "/events")
        for entityId in events.keys():
            health_state = "OK"
            detailed_msg = ""
            self.log.debug("Clearing the health state for entity {0} with health: {1}".format(entityId, health_state))
            self.create_event(entityId, health_state, detailed_msg)
        self.state.clear(self.url)

    def create_health_event(self, entityId, open_events):
        """
        Process each severity level of the events for an entityId and create the event with highest health state
        :param entityId: EntityId for which different events are considered
        :param open_events: Open events with different severity level for an EntityId
        """
        health_states = {"UNKNOWN": 0, "OK": 1, "DEVIATING": 2, "CRITICAL": 3}
        severity_level = {"AVAILABILITY": "DEVIATING", "CUSTOM_ALERT": "DEVIATING", "PERFORMANCE": "DEVIATING",
                          "RESOURCE_CONTENTION": "DEVIATING", "ERROR": "CRITICAL", "MONITORING_UNAVAILABLE": "CRITICAL"}
        health_state = "UNKNOWN"
        detailed_msg = """|  EventType  |  SeverityLevel  |  Impact  |  Open Since  |  Tags  |  Source  |\n
        |-------------|-----------------|----------|--------------|--------|----------|\n
        """
        for events in open_events:
            severity = events.get("severityLevel")
            impact = events.get("impactLevel")
            event_type = events.get("eventType")
            event_health_state = severity_level.get(severity)
            open_since = (datetime.fromtimestamp(events.get("startTime")/1000)).strftime("%b %-d, %Y, %H:%M:%S")
            tags = json.dumps(events.get("tags"), sort_keys=True)
            events_source = "dynatrace-"+events.get("source")
            detailed_msg += "|  {0}  |  {1}  |  {2}  |  {3}  |  {4}  |  {5}  |\n" \
                            "".format(event_type, severity, impact, open_since, tags, events_source)
            if health_states.get(event_health_state) > health_states.get(health_state):
                health_state = event_health_state
        self.log.debug("Logging an event for entity {0} with health: {1}".format(entityId, health_state))
        self.create_event(entityId, health_state, detailed_msg)

    def should_stop_processing(self, events_processed):
        """
        Check if we processed `events_process_limit` then stop the events processing
        :param events_processed: Total number of events processed so far
        :return: boolean True or False
        """
        if events_processed == self.events_process_limit:
            return True

    def create_event(self, entity_id, healthState, detailedmsg):
        """
        Create an event based on the data coming in from entity_event
        """
        tags = [
            "entityId:{0}".format(entity_id),
            "health:{0}".format(healthState)
        ]
        self.event({
            "timestamp": self._current_time_seconds(),
            "source_type_name": "Dynatrace Events",
            "msg_title": "",
            "msg_text": detailedmsg,
            "tags": tags
        })

    @staticmethod
    def _current_time_seconds():
        """
        This method is mocked for testing. Do not change its behavior
        :return: current timestamp
        """
        return int(time.time())

    def get_json_response(self, endpoint, timeout=10):
        headers = {"Authorization": "Api-Token {}".format(self.token)}
        resp = None
        msg = None
        try:
            session = Session()
            session.headers.update(headers)
            session.verify = self.verify
            if self.cert:
                session.cert = (self.cert, self.keyfile)
            resp = session.get(endpoint)
        except requests.exceptions.Timeout:
            msg = "{} seconds timeout when hitting {}".format(timeout, endpoint)
            raise Exception("Exception occured for endpoint {0} with message: {1}".format(endpoint, msg))
        return yaml.safe_load(resp.text)
