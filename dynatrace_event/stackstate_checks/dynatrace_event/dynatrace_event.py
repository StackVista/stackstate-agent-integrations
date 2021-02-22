# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time
from datetime import datetime, timedelta

from requests import Session
from requests.exceptions import Timeout
from schematics import Model
from schematics.types import StringType, IntType, ListType, URLType, BooleanType, ModelType, DictType

from stackstate_checks.base import AgentCheck, StackPackInstance

VERIFY_HTTPS = True
EVENTS_BOOSTRAP_DAYS_DEFAULT = 5
EVENTS_PROCESS_LIMIT_DEFAULT = 10000
TIMEOUT_DEFAULT = 10


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
    tags = ListType(DictType(StringType))
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
    timeout = IntType(default=TIMEOUT_DEFAULT)
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
                # Create state on the first run
                empty_state_timestamp = self._generate_bootstrap_timestamp(instance_info.events_boostrap_days)
                self.log.debug('Creating new empty state with timestamp: %s', empty_state_timestamp)
                instance_info.state = State({'last_processed_event_timestamp': empty_state_timestamp})
            self._process_events(instance_info)
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=instance_info.instance_tags,
                               message="Dynatrace events processed successfully")
        except EventLimitReachedException as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.WARNING, tags=instance_info.instance_tags,
                               message=str(e))
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance_info.instance_tags,
                               message=str(e))

    def _process_events(self, instance_info):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        events, events_limit_reached = self._collect_events(instance_info)
        closed_events = len([e for e in events if e.get('eventStatus') == 'CLOSED'])
        open_events = len([e for e in events if e.get('eventStatus') == 'OPEN'])
        self.log.info("Collected %d events, %d are open and %d are closed.", len(events), open_events, closed_events)
        for event in events:
            self._create_event(event, instance_info.url)
        if events_limit_reached:
            raise EventLimitReachedException(events_limit_reached)

    def _create_event(self, dynatrace_event, instance_url):
        """
        Create an standard or custom event based on the Dynatrace Severity level
        """
        event = {
            "timestamp": self._current_time_seconds(),
            "source_type_name": "Dynatrace Events",
            "msg_title": dynatrace_event.eventType + " on " + dynatrace_event.entityName,
            "msg_text": dynatrace_event.eventType + " on " + dynatrace_event.entityName,
            "tags": [
                "entityId:{0}".format(dynatrace_event.entityId),
                "severityLevel:{0}".format(dynatrace_event.severityLevel),
                "eventType:{0}".format(dynatrace_event.eventType),
                "impactLevel:{0}".format(dynatrace_event.impactLevel),
                "eventStatus:{0}".format(dynatrace_event.eventStatus),
                "startTime:{0}".format(dynatrace_event.startTime),
                "endTime:{0}".format(dynatrace_event.endTime),
                "source:{0}".format(dynatrace_event.source)
            ]
        }

        # Events with a info severity are send as custom events
        if dynatrace_event.severityLevel == 'INFO':
            event["context"] = {
                "source_identifier": "source_identifier_value",
                "element_identifiers": ["urn:{}".format(dynatrace_event.entityId)],
                "source": "dynatrace",
                "category": "info_event",
                "data": dynatrace_event.to_primitive(),
                "source_links": [
                    # TODO the real event external link
                    {"title": "my_event_external_link", "url": instance_url}
                ]
            }

        self.event(event)

    def _collect_events(self, instance_info):
        """
        Checks for EventLimitReachedException and process each event API response for next cursor
        until is None or it reach events_process_limit
        """
        events_response = self._get_events(instance_info, from_time=instance_info.state.last_processed_event_timestamp)
        if "error" in events_response:
            raise Exception("Error in pulling the events: {}".format(events_response.get("error").get("message")))
        new_events = []
        events_processed = 0
        event_limit_reached = None
        try:
            while events_response:
                events = events_response.get('events', [])
                for event in events:
                    dynatrace_event = DynatraceEvent(event, strict=False)
                    dynatrace_event.validate()
                    new_events.append(dynatrace_event)
                    events_processed += 1
                    self._check_event_limit_exceeded_condition(instance_info, events_processed)
                if events_response.get("nextCursor"):
                    events_response = self._get_events(instance_info, cursor=events_response.get("nextCursor"))
                else:
                    instance_info.state.last_processed_event_timestamp = events_response.get("to")
                    events_response = None
        except EventLimitReachedException as e:
            instance_info.state.last_processed_event_timestamp = events_response.get("to")
            event_limit_reached = str(e)
        return new_events, event_limit_reached

    def _get_events(self, instance_info, from_time=None, cursor=None):
        """
        Get events from Dynatrace Event API endpoint
        :param instance_info: object with instance info and its state
        :param from_time: timestamp from which to collect events
        :param cursor:
        :return: Event API endpoint response
        """
        params = {}
        if from_time:
            params['from'] = from_time
        if cursor:
            params['cursor'] = cursor
        endpoint = instance_info.url + "/api/v1/events"
        events = self._get_dynatrace_event_json_response(instance_info, endpoint, params)
        return events

    @staticmethod
    def _check_event_limit_exceeded_condition(instance_info, total_event_count):
        """
        Raises EventLimitReachedException if number of events between subsequent check runs
        exceed the `events_process_limit`
        """
        if total_event_count >= instance_info.events_process_limit:
            raise EventLimitReachedException("Maximum event limit to process is {} but received total {} events".
                                             format(instance_info.events_process_limit, total_event_count))

    @staticmethod
    def _generate_bootstrap_timestamp(days):
        """
        Creates timestamp n days in the past from the current moment. It is used in tests too.
        :param days: how many days in the past
        :return:
        """
        bootstrap_date = datetime.now() - timedelta(days=days)
        return int(bootstrap_date.strftime('%s')) * 1000

    @staticmethod
    def _current_time_seconds():
        """
        This method is mocked for testing. Do not change its behavior
        :return: current timestamp
        """
        return int(time.time())

    @staticmethod
    def _get_dynatrace_event_json_response(instance_info, endpoint, params):
        headers = {"Authorization": "Api-Token {}".format(instance_info.token)}
        try:
            with Session() as session:
                session.headers.update(headers)
                session.verify = instance_info.verify
                if instance_info.cert:
                    session.cert = (instance_info.cert, instance_info.keyfile)
                resp = session.get(endpoint, params=params)
                if resp.status_code != 200:
                    raise Exception("Got %s when hitting %s" % (resp.status_code, endpoint))
                return resp.json()
        except Timeout:
            msg = "{} seconds timeout".format(instance_info.timeout)
            raise Exception("Exception occurred for endpoint {0} with message: {1}".format(endpoint, msg))


class EventLimitReachedException(Exception):
    """
    Exception raised when maximum number of event reached
    """
    pass
