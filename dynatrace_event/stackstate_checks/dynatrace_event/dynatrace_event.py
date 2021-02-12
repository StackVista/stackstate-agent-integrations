# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time
from datetime import datetime, timedelta

import yaml
from requests import Session
from requests.exceptions import Timeout
from schematics import Model
from schematics.types import StringType, IntType, ListType, DateTimeType, URLType, BooleanType, ModelType

from stackstate_checks.base import AgentCheck, StackPackInstance

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
    last_processed_event_timestamp = IntType(required=True)


class InstanceInfo(Model):
    url = URLType(required=True)
    token = StringType(required=True)
    instance_tags = ListType(StringType, default=[])
    events_boostrap_days = IntType(default=EVENTS_BOOSTRAP_DAYS_DEFAULT)
    events_process_limit = IntType(default=EVENTS_PROCESS_LIMIT_DEFAULT)
    verify = BooleanType(default=VERIFY_HTTPS)
    cert = StringType()
    keyfile = StringType()
    state = ModelType(State)


class DynatraceEventCheck(AgentCheck):
    INSTANCE_TYPE = "dynatrace_event"
    SERVICE_CHECK_NAME = "dynatrace_event"
    INSTANCE_SCHEMA = InstanceInfo

    def get_instance_key(self, instance_info):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance_info.url))

    def check(self, instance_info):
        try:
            if not instance_info.state:
                # Create empty state
                bootstrap_date = datetime.now() - timedelta(days=instance_info.events_boostrap_days)
                empty_state_timestamp = int(bootstrap_date.strftime('%s')) * 1000
                instance_info.state = State(
                    {
                        'last_processed_event_timestamp': empty_state_timestamp

                    }
                )
            self.process_events(instance_info)
            msg = "Dynatrace events processed successfully"
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=instance_info.instance_tags, message=msg)
        except EventLimitReachedException as e:
            # TODO Is this CRITICAL error?!?!
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance_info.instance_tags,
                               message=str(e))
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance_info.instance_tags,
                               message=str(e))

    def process_events(self, instance_info):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        events = self.collect_events(instance_info)
        self.log.debug("Collected %d", len(events))
        for event in events:
            self.new_create_event(event)

    def get_events(self, instance_info, from_time=None, cursor=None):
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
        endpoint = instance_info.url + "/api/v1/events{}".format(params)
        events = self.get_dynatrace_event_json_response(instance_info, endpoint)
        return events

    def collect_events(self, instance_info):
        """
        Checks for EventLimitReachedException and process each event API response for next cursor
        until is None or it reach events_process_limit
        """
        events_response = self.get_events(instance_info, from_time=instance_info.state.last_processed_event_timestamp)
        total_event_count = events_response.get("totalEventCount", 0)
        if self.event_limit_exceeded_condition(instance_info, total_event_count):
            raise EventLimitReachedException("Maximum event limit to process is {} but received total {} events".
                                             format(instance_info.events_process_limit, total_event_count))
        events = []
        events_processed = 0
        while events_response:
            for event in events_response.get('events', []):
                dynatrace_event = DynatraceEvent(event, strict=False)
                dynatrace_event.validate()
                events.append(dynatrace_event)
            events_processed += len(events_response)
            if events_response.get("nextCursor") and events_processed < instance_info.events_process_limit:
                events_response = self.get_events(instance_info, cursor=events_response.get("nextCursor"))
            else:
                instance_info.state.last_processed_event_timestamp = events_response.get("to")
                events_response = None
        return events

    def event_limit_exceeded_condition(self, instance_info, total_event_count):
        """
        Check if number of events between subsequent check runs exceed the `events_process_limit`
        :return: boolean True or False
        """
        # if events processed last time and total event count exceeded the limit
        if instance_info.state.last_processed_event_timestamp is not None and \
                total_event_count >= instance_info.events_process_limit:
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

    def get_dynatrace_event_json_response(self, instance_info, endpoint, timeout=10):
        headers = {"Authorization": "Api-Token {}".format(instance_info.token)}
        try:
            with Session() as session:
                session.headers.update(headers)
                session.verify = instance_info.verify
                if instance_info.cert:
                    session.cert = (instance_info.cert, instance_info.keyfile)
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
