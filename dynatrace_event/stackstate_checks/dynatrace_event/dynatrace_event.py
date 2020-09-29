# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance
from .util import DynatraceData

import requests
import yaml
from datetime import datetime, timedelta
import time


class DynatraceEventCheck(AgentCheck):

    INSTANCE_TYPE = "dynatrace_event"
    SERVICE_CHECK_NAME = "dynatrace_event"

    def __init__(self, name, init_config, instances=None):
        AgentCheck.__init__(self, name, init_config, instances)
        self.url = None
        self.token = None
        self.tags = None
        self.environment = None
        self.events_start_days = None
        self.domain = None
        self.status = None

    def load_status(self):
        self.status = DynatraceData.load_latest_status()
        if self.status is None:
            self.status = DynatraceData()

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
        self.events_start_days = instance.get('events_start_days', 5)
        self.tags = instance.get('tags', [])
        self.environment = instance.get('environment', 'production')
        self.load_status()
        self.log.info("After loading the status: {}".format(self.status.data))
        self.log.info("After loading, the from time is {}".format(self.status.data.get(self.url)))

        try:
            self.start_snapshot()
            self.process_events()
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags, message=str(e))
        finally:
            self.stop_snapshot()

    def process_events(self):
        self.collect_events()
        self.send_filtered_events()
        self.log.info("Persisting the data...")
        self.status.persist()
        self.log.debug("Data in memory is: {}".format(self.status.data))

    def send_filtered_events(self):
        events = self.status.data.get(self.url + "/events")
        if events:
            for entityId in events.keys():
                open_events = []
                event_type_values = events.get(entityId)
                if event_type_values:
                    for event_type in event_type_values.keys():
                        event_status = event_type_values.get(event_type).get("eventStatus")
                        if event_status == "CLOSED":
                            # del event_type_values[event_type]
                            del self.status.data[self.url + "/events"][entityId][event_type]
                        else:
                            self.log.info("Appending an open event for entityID {}: {}".format(entityId, event_type_values[event_type]))
                            open_events.append(event_type_values[event_type])
                    if not self.status.data[self.url + "/events"][entityId]:
                        del self.status.data[self.url + "/events"][entityId]
                    if len(open_events) > 0:
                        self.create_health_event(entityId, open_events)
                else:
                    # del events[entityId]
                    del self.status.data[self.url + "/events"][entityId]
        self.log.info("After filtering the closed events :- {}".format(self.status.data))

    def create_health_event(self, entityId, open_events):
        health_states = {"UNKNOWN": 0, "OK": 1, "DEVIATING": 2, "CRITICAL": 3}
        severity_level = {"AVAILABILITY": "OK", "CUSTOM_ALERT": "OK", "PERFORMANCE": "DEVIATING",
                          "RESOURCE_CONTENTION": "DEVIATING", "ERROR": "CRITICAL", "MONITORING_UNAVAILABLE": "CRITICAL"}
        health_state = "UNKNOWN"
        detailed_msg = """|  EventType  |  SeverityLevel  |  Impact  |\n
        |-------------|-----------------|----------|\n
        """
        for events in open_events:
            severity = events.get("severityLevel")
            impact = events.get("impactLevel")
            event_type = events.get("eventType")
            entity_name = events.get("entityName")
            event_health_state = severity_level.get(severity)
            detailed_msg += "|    {0}     |   {1}    |   {2}   |\n".format(event_type, severity, impact)
            if health_states.get(event_health_state) > health_states.get(health_state):
                health_state = event_health_state

        self.log.info("Logging an event for entity {0} with message: {1}".format(entity_name, detailed_msg))
        self.create_event(entityId, health_state, detailed_msg)

    def collect_events(self, cursor=''):
        """
        Process events from Dynatrace
        """
        # Check in memory if we received events from the instance and last received time which will become from_time
        # in the next time check runs
        from_time = self.status.data.get(self.url)
        if not from_time:
            from_time = int((datetime.now() - timedelta(days=self.events_start_days)).strftime('%s'))*1000
        to_time = int(datetime.now().strftime('%s'))*1000
        params = "?from={0}&to={1}".format(from_time, to_time)
        if cursor:
            params = "?cursor={}".format(cursor)
            endpoint = self.url + "/api/v1/events{}".format(params)
        else:
            endpoint = self.url + "/api/v1/events{}".format(params)
        events = self.get_json_response(endpoint)
        if "error" not in events:
            for item in events["events"]:
                entityId = item.get("entityId")
                event_status = item.get("eventStatus")
                start_time = int(item.get("startTime"))
                event_type = item.get("eventType")
                # Create an event when no event exist for that entityId
                state_events = self.status.data.get(self.url+"/events", {})
                if self.url + "/events" not in self.status.data:
                    self.status.data[self.url+"/events"] = {}
                entity_events = state_events.get(entityId)
                if entity_events is None:
                    self.log.info("Creating a new open event type for an existing entityId")
                    self.status.data[self.url + "/events"][entityId] = {event_type: item}
                # Check if event already exist for that entityId
                elif entity_events:
                    event = entity_events.get(event_type)
                    end_time = entity_events.get(event_type, {}).get("endTime")
                    status = entity_events.get(event_type, {}).get("eventStatus")
                    # different type of event can exist for same entityId
                    if event is None and event_status == "OPEN":
                        self.log.info("Creating a new open event type for an existing entityId")
                        self.status.data[self.url + "/events"][entityId][event_type] = item
                    # new event for same entityId with latest time
                    elif start_time > end_time and status == event_status:
                        self.log.info("Updating the existing event type for an existing entityId with new event")
                        del self.status.data[self.url + "/events"][entityId][event_type]
                        self.status.data[self.url + "/events"][entityId][event_type] = item
                    # new event with CLOSED status come in for existing OPEN event for an even type of that entityId
                    elif status == "CLOSED" and event_status == "OPEN":
                        self.log.info("Deleting an existing open event type for an existing entityId ")
                        del self.status.data[self.url + "/events"][entityId][event_type]
            nextCursor = events.get("nextCursor")
            self.log.info("Next cursor value is {}".format(nextCursor))
            if nextCursor:
                self.log.info("Next cursor is not null, so recursing again...")
                self.collect_events(cursor=nextCursor)
        else:
            self.log.debug("Error in pulling the events : {}".format(events.get("error").get("message")))
        # push the last received timestamp in memory for the instance
        self.status.data[self.url] = events.get("to")

    def create_event(self, entity_id, healthState, detailedmsg):
        """
        Create an event based on the data coming in from entity_event
        """
        self.log.info("Creating a new event")
        tags = [
            "entityId:{0}".format(entity_id),
            "health:{0}".format(healthState)
        ]
        self.event({
            "timestamp": int(time.time()),
            "source_type_name": "Dynatrace Events",
            "msg_title": "",
            "msg_text": detailedmsg,
            "tags": tags
        })

    def get_json_response(self, endpoint, timeout=10):
        headers = {"Authorization": "Api-Token {}".format(self.token)}
        status = None
        resp = None
        msg = None
        self.log.info("URL is {}".format(endpoint))
        self.log.info("Header is {}".format(headers))
        try:
            resp = requests.get(endpoint, headers=headers)
        except requests.exceptions.Timeout:
            msg = "{} seconds timeout when hitting {}".format(timeout, endpoint)
            status = AgentCheck.CRITICAL
        except Exception as e:
            msg = str(e)
            status = AgentCheck.CRITICAL
        finally:
            if status is AgentCheck.CRITICAL:
                self.service_check(self.SERVICE_CHECK_NAME, status, tags=[],
                                   message=msg)
                raise Exception("Exception occured for endpoint {0} with message: {1}".format(endpoint, msg))
        return yaml.safe_load(resp.text)
