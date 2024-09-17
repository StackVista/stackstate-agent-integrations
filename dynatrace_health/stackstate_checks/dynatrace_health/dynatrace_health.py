# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time
from datetime import datetime, timedelta

from stackstate_checks.base.utils.validations_utils import CheckBaseModel
from schematics.types import IntType, StringType, ListType, DictType, URLType, BooleanType, ModelType

from stackstate_checks.base import StackPackInstance, HealthStream, HealthStreamUrn, Health, Identifiers
from stackstate_checks.checks import AgentCheck
from stackstate_checks.dynatrace.dynatrance_client import DynatraceClient

VERIFY_HTTPS = True
TIMEOUT = 10
EVENTS_BOOSTRAP_DAYS = 5
EVENTS_PROCESS_LIMIT = 10000
RELATIVE_TIME = 'hour'

DYNATRACE_UI_URLS = {
    "SERVICE": "%s/#newservices/serviceOverview;id=%s",
    "PROCESS_GROUP": "%s/#processgroupdetails;id=%s",
    "PROCESS_GROUP_INSTANCE": "%s/#processdetails;id=%s",
    "PROCESS": "%s/#processdetails;id=%s",
    "HOST": "%s/#newhosts/hostdetails;id=%s",
    "APPLICATION": "%s/#uemapplications/uemappmetrics;uemapplicationId=%s",
    "CUSTOM_DEVICE": "%s/#customdevicegroupdetails/entity;id=%s"
}


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
    events_boostrap_days = IntType(default=EVENTS_BOOSTRAP_DAYS)
    events_process_limit = IntType(default=EVENTS_PROCESS_LIMIT)
    verify = BooleanType(default=VERIFY_HTTPS)
    cert = StringType()
    keyfile = StringType()
    timeout = IntType(default=TIMEOUT)
    relative_time = StringType(default=RELATIVE_TIME)
    state = ModelType(State)


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
                instance_info.state = State({'last_processed_event_timestamp': empty_state_timestamp})
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
        open_events = [e for e in events if e.get('eventStatus') == 'OPEN']
        closed_events = len(events) - len(open_events)
        self.log.info("Collected %d events, %d are open and %d are closed.", len(events), len(open_events),
                      closed_events)
        self.health.start_snapshot()
        for event in open_events:
            if event.severityLevel == 'INFO':
                # Events with a info severity are send as topology events
                link_to_entity = self.link_to_dynatrace(str(event.entityId), instance_info.url)
                self._create_topology_event(event, link_to_entity)
            else:
                # Create health state for other events
                if event.severityLevel in severity_levels_that_maps_to_deviating_health_state:
                    health_value = Health.DEVIATING
                elif event.severityLevel in severity_levels_that_maps_to_critical_health_state:
                    health_value = Health.CRITICAL
                else:
                    health_value = Health.CLEAR
                identifier = Identifiers.create_custom_identifier("dynatrace", event.entityId)
                self.health.check_state(
                    check_state_id=event.entityId,
                    name='Dynatrace event',
                    health_value=health_value,
                    topology_element_identifier=identifier,
                    message='Event: {} Severity: {} Impact: {} Open Since: {} Source: {}'.format(
                        event.eventType, event.severityLevel, event.impactLevel,
                        datetime.fromtimestamp(int(event.startTime) / 1000).strftime(
                            "%b %-d, %Y, %H:%M:%S"), event.source
                    )
                )
        self.health.stop_snapshot()
        if events_limit_reached:
            raise EventLimitReachedException(events_limit_reached)

    def _create_topology_event(self, dynatrace_event, link_to_entity):
        """
        Create an standard or custom event based on the Dynatrace Severity level
        """
        event = {
            "timestamp": int(time.time()),
            "source_type_name": "Dynatrace Events",
            "msg_title": "%s on %s" % (dynatrace_event.eventType, dynatrace_event.entityName),
            "msg_text": "%s on %s" % (dynatrace_event.eventType, dynatrace_event.entityName),
            "tags": [
                "entityId:%s" % dynatrace_event.entityId,
                "severityLevel:%s" % dynatrace_event.severityLevel,
                "eventType:%s" % dynatrace_event.eventType,
                "impactLevel:%s" % dynatrace_event.impactLevel,
                "eventStatus:%s" % dynatrace_event.eventStatus,
                "startTime:%s" % dynatrace_event.startTime,
                "endTime:%s" % dynatrace_event.endTime,
                "source:%s" % dynatrace_event.source,
                "openSince:%s" % datetime.fromtimestamp(dynatrace_event.startTime / 1000).strftime(
                    "%b %-d, %Y, %H:%M:%S"),
            ],
            "context": {
                "source_identifier": "source_identifier_value",
                "element_identifiers": ["urn:%s" % dynatrace_event.entityId],
                "source": "dynatrace",
                "category": "info_event",
                "data": dynatrace_event.to_primitive(),
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
                events = events_response.get('events', [])
                for event in events:
                    dynatrace_event = DynatraceEvent(event, strict=False)
                    dynatrace_event.validate()
                    new_events.append(dynatrace_event)
                    events_processed += 1
                    self._check_event_limit_exceeded_condition(instance_info.events_process_limit, events_processed)
                if events_response.get("nextCursor"):
                    events_response = self._get_events(dynatrace_client, instance_info.url,
                                                       cursor=events_response.get("nextCursor"))
                else:
                    instance_info.state.last_processed_event_timestamp = events_response.get("to")
                    events_response = None
        except EventLimitReachedException as e:
            instance_info.state.last_processed_event_timestamp = events_response.get("to")
            event_limit_reached = str(e)
        return new_events, event_limit_reached

    def _get_events(self, dynatrace_client, url, from_time=None, cursor=None):
        """
        Get events from Dynatrace Event API endpoint
        :param dynatrace_client: dynatrace rest client
        :param url: dynatrace instance url
        :param from_time: timestamp from which to collect events
        :param cursor: batch cursor
        :return: Event API endpoint response
        """
        params = {}
        if from_time:
            params['from'] = from_time
        if cursor:
            params['cursor'] = cursor
        endpoint = dynatrace_client.get_endpoint(url, "/api/v1/events")
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
        try:
            url = DYNATRACE_UI_URLS[entity_type] % (instance_url, entity_id)
            return url
        except KeyError:
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
