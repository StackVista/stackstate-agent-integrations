# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time
from datetime import datetime, timedelta
from typing import Optional, List
from stackstate_checks.base.utils.validations_utils import ForgivingBaseModel, AnyUrlStr

from stackstate_checks.base import StackPackInstance, HealthStream, HealthStreamUrn, Health, Identifiers
from stackstate_checks.checks import AgentCheck
from stackstate_checks.dynatrace.dynatrace_client import DynatraceClient
from stackstate_checks.dynatrace_health.event_data_types import DynatraceEvent

VERIFY_HTTPS = True
TIMEOUT = 10
EVENTS_BOOSTRAP_DAYS = 5
EVENTS_PROCESS_LIMIT = 10000
RELATIVE_TIME = '1h'

TOPOLOGY_API_SPEC = {
    "SERVICE": ("api/v2/events", 'type("SERVICE")'),
    "PROCESS-GROUP": ("api/v2/events", 'type("PROCESS_GROUP")'),
    "PROCESS_GROUP_INSTANCE": ("api/v2/events", 'type("PROCESS_GROUP_INSTANCE")'),
    "PROCESS": ("api/v2/events", 'type("PROCESS_GROUP_INSTANCE")'),
    "HOST": ("api/v2/events", 'type("HOST")'),
    "APPLICATION": ("api/v2/events", 'type("APPLICATION")'),
    "CUSTOM-DEVICE": ("api/v2/events", 'type("CUSTOM_DEVICE")'),
}


class State(ForgivingBaseModel):
    last_processed_event_timestamp: int


class InstanceInfo(ForgivingBaseModel):
    url: AnyUrlStr
    token: str
    instance_tags: List[str] = []
    events_boostrap_days: int = EVENTS_BOOSTRAP_DAYS
    events_process_limit: int = EVENTS_PROCESS_LIMIT
    verify: bool = VERIFY_HTTPS
    cert: Optional[str] = None
    keyfile: Optional[str] = None
    timeout: int = TIMEOUT
    relative_time: str = RELATIVE_TIME
    state: Optional[State] = None


class DynatraceHealthCheck(AgentCheck):
    INSTANCE_TYPE = "dynatrace"
    SERVICE_CHECK_NAME = "dynatrace-health"
    INSTANCE_SCHEMA = InstanceInfo

    def get_instance_key(self, instance_info):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance_info.url))

    def get_health_stream(self, instance):
        return HealthStream(HealthStreamUrn(self.INSTANCE_TYPE, 'dynatrace-events'))

    def check(self, instance_info):
        try:
            if not instance_info.state:
                # Create state on the first run
                empty_state_timestamp = self.generate_bootstrap_timestamp(instance_info.events_boostrap_days)
                self.log.debug('Creating new empty state with timestamp: %s', empty_state_timestamp)
                instance_info.state = State(**{'last_processed_event_timestamp': empty_state_timestamp})
            dynatrace_client = DynatraceClient(instance_info.token,
                                               instance_info.verify,
                                               instance_info.cert,
                                               instance_info.keyfile,
                                               instance_info.timeout)
            self._process_events(dynatrace_client, instance_info)
            msg = "Dynatrace health check processed successfully"
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=instance_info.instance_tags, message=msg)
        except EventLimitReachedException as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.WARNING, tags=instance_info.instance_tags,
                               message=str(e))
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance_info.instance_tags,
                               message=str(e))

    def _process_events(self, dynatrace_client, instance_info):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        severity_levels_that_maps_to_deviating_health_state = ["PERFORMANCE", "RESOURCE_CONTENTION",
                                                               "MONITORING_UNAVAILABLE", "ERROR"]
        severity_levels_that_maps_to_critical_health_state = ["AVAILABILITY", "CUSTOM_ALERT"]
        events, events_limit_reached = self._collect_events(dynatrace_client, instance_info)
        open_events_count = len([e for e in events if e.status == 'OPEN'])
        closed_events_count = len(events) - open_events_count
        self.log.info("Collected %d events, %d are open and %d are closed.", len(events), open_events_count,
                      closed_events_count)
        self.health.start_snapshot()
        for event in events:
            # Get the event Type definition from the API.
            endpoint = f"{instance_info.url}/api/v2/eventTypes/{event.eventType}"
            event_type_data = dynatrace_client.get_dynatrace_json_response(endpoint, None)
            display_name = event_type_data.get('displayName', event.eventType)
            severity_level = event_type_data.get('severityLevel', 'INFO')
            impact = "Unspecified"
            source = "builtin"
            for ppty in event.properties:
                if ppty.key == 'impactLevel':
                    impact = ppty.value
                if ppty.key == 'source':
                    source = ppty.value
            if severity_level == 'INFO':
                # Events with a info severity are send as topology events
                entity_id = event.entityId.entityId.id
                entity_endpoint = f"{instance_info.url}/api/v2/entities/{entity_id}"
                entity_data = dynatrace_client.get_dynatrace_json_response(entity_endpoint, None)
                link_to_entity = self.link_to_dynatrace(entity_id, instance_info.url)
                self._create_topology_event(event, link_to_entity, severity_level, entity_data, impact, display_name)
            elif event.status == 'OPEN':
                # Create health state for other events that are OPEN
                if severity_level in severity_levels_that_maps_to_deviating_health_state:
                    health_value = Health.DEVIATING
                elif severity_level in severity_levels_that_maps_to_critical_health_state:
                    health_value = Health.CRITICAL
                else:
                    health_value = Health.CLEAR
                identifier = Identifiers.create_custom_identifier("dynatrace", event.entityId.entityId.id)
                self.health.check_state(
                    check_state_id=event.entityId.entityId.id,
                    name='Dynatrace event',
                    health_value=health_value,
                    topology_element_identifier=identifier,
                    message='Event: {} Severity: {} Impact: {} Open Since: {} Source: {}'.format(
                        display_name, severity_level, impact,
                        datetime.fromtimestamp(int(event.startTime) / 1000).strftime(
                            "%b %-d, %Y, %H:%M:%S"), source
                    )
                )
        self.health.stop_snapshot()
        if events_limit_reached:
            raise EventLimitReachedException(events_limit_reached)

    def _create_topology_event(self, dynatrace_event, link_to_entity, severity_level, entity_data, impact,
                               event_display_name):
        """
        Create an standard or custom event based on the Dynatrace Severity level
        """
        event = {
            "timestamp": int(time.time()),
            "source_type_name": "Dynatrace Events",
            "msg_title": "%s on %s" % (event_display_name, entity_data.get('displayName')),
            "msg_text": "%s on %s" % (event_display_name, entity_data.get('displayName')),
            "tags": [
                "entityId:%s" % dynatrace_event.entityId,
                "severityLevel:%s" % severity_level,
                "eventType:%s" % dynatrace_event.eventType,
                "impactLevel:%s" % impact,
                "eventStatus:%s" % dynatrace_event.status,
                "startTime:%s" % dynatrace_event.startTime,
                "endTime:%s" % dynatrace_event.endTime,
                # "source:%s" % dynatrace_event.source,
                "openSince:%s" % datetime.fromtimestamp(dynatrace_event.startTime / 1000).strftime(
                    "%b %-d, %Y, %H:%M:%S"),
            ],
            "context": {
                "source_identifier": "source_identifier_value",
                "element_identifiers": ["urn:%s" % dynatrace_event.entityId.entityId.id],
                "source": "dynatrace",
                "category": "info_event",
                "data": dynatrace_event.dict(),
                "source_links": [
                    {
                        "title": "my_event_external_link",
                        "url": link_to_entity
                    }
                ]
            }
        }
        self.event(event)

    def _collect_events(self, dynatrace_client, instance_info):
        """
        Checks for EventLimitReachedException and process each event API response for next cursor
        until is None or it reach events_process_limit
        """
        events_response = self._get_events(dynatrace_client, instance_info.url,
                                           from_time=instance_info.state.last_processed_event_timestamp)
        new_events = []
        events_processed = 0
        event_limit_reached = None
        try:
            while events_response:
                if type(events_response) is dict:
                    events = events_response.get('events', [])
                else:
                    events = events_response
                for event in events:
                    dynatrace_event = DynatraceEvent(**event)
                    new_events.append(dynatrace_event)
                    events_processed += 1
                    self._check_event_limit_exceeded_condition(instance_info.events_process_limit, events_processed)
                if events_response.get("nextPageKey"):
                    events_response = self._get_events(dynatrace_client, instance_info.url,
                                                       next_page_key=events_response.get("nextPageKey"))
                else:
                    instance_info.state.last_processed_event_timestamp = events_response.get("to")
                    events_response = None
        except EventLimitReachedException as e:
            instance_info.state.last_processed_event_timestamp = events_response.get("to")
            event_limit_reached = str(e)
        return new_events, event_limit_reached

    def _get_events(self, dynatrace_client, url, from_time=None, next_page_key=None):
        """
        Get events from Dynatrace Event API endpoint
        :param dynatrace_client: dynatrace rest client
        :param url: dynatrace instance url
        :param from_time: timestamp from which to collect events
        :param next_page_key: batch cursor
        :return: Event API endpoint response
        """
        params = {}
        if from_time:
            params['from'] = from_time
        if next_page_key:
            params['nextPageKey'] = next_page_key
        endpoint = dynatrace_client.get_endpoint(url, "/api/v2/events")
        events = dynatrace_client.get_dynatrace_json_response(endpoint, params)
        self.log.debug('Got %s events from %s', len(events.get('events', [])), endpoint)
        return events

    @staticmethod
    def _check_event_limit_exceeded_condition(events_process_limit, total_event_count):
        """
        Raises EventLimitReachedException if number of events between subsequent check runs
        exceed the `events_process_limit`
        """
        if total_event_count > events_process_limit:
            raise EventLimitReachedException("Maximum event limit to process is %s but received total %s events"
                                             % (events_process_limit, total_event_count))

    @staticmethod
    def link_to_dynatrace(entity_id, instance_url):
        """
        Compose url to dynatrace entity page, if not able return link to Dynatrace instance.
        :param entity_id: Dynatrace entity identifier
        :param instance_url: Dynatrace instance url
        :return: url to Dynatrace entity page.
        """
        entity_type = entity_id.split("-")[0]
        if entity_type != "UNKNOWN":
            return f"{instance_url}/api/v2/entities/{entity_id}"
        else:
            return instance_url

    @staticmethod
    def generate_bootstrap_timestamp(days):
        """
        Creates timestamp n days in the past from the current moment. It is used in tests too.
        :param days: how many days in the past
        :return:
        """
        bootstrap_date = datetime.fromtimestamp(int(time.time())) - timedelta(days=days)
        return int(bootstrap_date.strftime('%s')) * 1000


class EventLimitReachedException(Exception):
    """
    Exception raised when maximum number of event reached
    """
    pass
