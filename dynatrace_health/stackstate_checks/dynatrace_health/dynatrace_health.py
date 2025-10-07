# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os
import time
from datetime import datetime, timedelta
from typing import Optional, List
from stackstate_checks.base.utils.validations_utils import ForgivingBaseModel, AnyUrlStr

from stackstate_checks.base import StackPackInstance, HealthStream, HealthStreamUrn, Health, Identifiers
from stackstate_checks.checks import AgentCheck
from stackstate_checks.dynatrace.dynatrace_client import DynatraceClientFactory
from stackstate_checks.dynatrace.constants import SUPPORTED_ENTITY_TYPES_PARAM_SELECTORS
from stackstate_checks.dynatrace_health.event_data_types import DynatraceEvent

VERIFY_HTTPS = True
TIMEOUT = 10
EVENTS_BOOSTRAP_DAYS = 5
EVENTS_PROCESS_LIMIT = 10000
RELATIVE_TIME = '1h'


class State(ForgivingBaseModel):
    last_processed_event_timestamp: Optional[int] = None


class InstanceInfo(ForgivingBaseModel):
    url: AnyUrlStr
    token: str
    instance_tags: List[str] = []
    collection_interval: int = 300  # Check interval in seconds, default 300s
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

    def __init__(self, name, init_config, instances):
        super(DynatraceHealthCheck, self).__init__(name, init_config, instances)
        self.dynatrace_client_factory = DynatraceClientFactory()
        # Simple in-memory cache for event type definitions within the check lifecycle
        # key: event type string, value: dict returned by the Dynatrace API
        self._event_type_cache = {}

    def get_instance_key(self, instance_info):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance_info.url))

    def get_health_stream(self, instance):
        return HealthStream(HealthStreamUrn(self.INSTANCE_TYPE, 'dynatrace-events'))

    def check(self, instance_info):
        try:
            self.log.info("State at check start: %s", instance_info.state)
            if instance_info.state:
                self.log.info("State.last_processed_event_timestamp: %s",
                              instance_info.state.last_processed_event_timestamp)

            if not instance_info.state or not instance_info.state.last_processed_event_timestamp:
                # Create state on the first run
                empty_state_timestamp = self.generate_bootstrap_timestamp(instance_info.events_boostrap_days)
                self.log.info('Creating new empty state with timestamp: %s', empty_state_timestamp)
                instance_info.state = State(**{'last_processed_event_timestamp': empty_state_timestamp})
            else:
                # Validate that timestamp isn't too old (more than double the check interval)
                # This prevents processing too many events if state gets stale or corrupted
                current_time_ms = int(time.time() * 1000)
                last_timestamp_ms = instance_info.state.last_processed_event_timestamp

                # Use collection_interval from instance config (in seconds)
                collection_interval_sec = instance_info.collection_interval
                max_time_diff_ms = collection_interval_sec * 2 * 1000  # Double interval in milliseconds

                time_diff_ms = current_time_ms - last_timestamp_ms

                if time_diff_ms > max_time_diff_ms:
                    old_timestamp = last_timestamp_ms
                    new_timestamp = current_time_ms - max_time_diff_ms
                    instance_info.state.last_processed_event_timestamp = new_timestamp
                    self.log.info(
                        "Timestamp was too old (%d ms = %.1f days ago). "
                        "Capped to double check interval (%d seconds = %d ms). "
                        "Old timestamp: %d, New timestamp: %d",
                        time_diff_ms,
                        time_diff_ms / (1000 * 60 * 60 * 24),
                        collection_interval_sec * 2,
                        max_time_diff_ms,
                        old_timestamp,
                        new_timestamp
                    )

            dynatrace_client = self.dynatrace_client_factory.create_client(
                instance_name=str(instance_info.url),
                token=instance_info.token,
                verify=instance_info.verify,
                cert=instance_info.cert,
                keyfile=instance_info.keyfile,
                timeout=instance_info.timeout
            )
            if os.getenv('JWT_AUTH') == "true":
                instance_info.token = dynatrace_client.get_token()

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

    @staticmethod
    def _is_warmup_enabled():
        """
        Toggle cache warm-ups via env var DYNATRACE_HEALTH_ENABLE_WARMUP (default: true)
        """
        return os.getenv('DYNATRACE_HEALTH_ENABLE_WARMUP', 'true').lower() == 'true'

    def _process_events(self, dynatrace_client, instance_info):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        severity_levels_that_maps_to_deviating_health_state = ["PERFORMANCE", "RESOURCE_CONTENTION",
                                                               "MONITORING_UNAVAILABLE", "ERROR"]
        severity_levels_that_maps_to_critical_health_state = ["AVAILABILITY", "CUSTOM_ALERT"]
        events, events_limit_reached = self._collect_events(dynatrace_client, instance_info)

        if events_limit_reached:
            events = events[:instance_info.events_process_limit]

        # Warm the event type cache with unique event types from this batch
        if self._is_warmup_enabled():
            try:
                unique_event_types = {e.eventType or 'UNKNOWN' for e in events}
                start_ts = time.time()
                self._warm_event_type_cache(dynatrace_client, str(instance_info.url), unique_event_types)
                self.log.info("Warmed event types cache, took %d seconds", int(time.time() - start_ts))
            except Exception as e:
                self.log.debug(f"Failed to warm event type cache: {e}")

        # Warm the entity cache by fetching ALL entities for supported types (store only displayName)
        if self._is_warmup_enabled():
            try:
                start_ts = time.time()
                self._warm_all_supported_entities(
                    dynatrace_client,
                    str(instance_info.url),
                    instance_info.relative_time or '1h'
                )
                self.log.info("Warmed entities cache, took %d seconds", int(time.time() - start_ts))
            except Exception as e:
                self.log.debug(f"Failed to warm all supported entities: {e}")

        open_events_count = len([e for e in events if e.status == 'OPEN'])
        closed_events_count = len(events) - open_events_count
        self.log.info("Collected %d events, %d are open and %d are closed.", len(events), open_events_count,
                      closed_events_count)

        # Dictionary to accumulate 404 errors per entity type
        entity_404_errors = {}
        # Set to track entity types that have caused 404 errors in this run
        problematic_entity_types = set()

        self.health.start_snapshot()
        for event in events:
            # Get the event Type definition from the API.
            event_type = event.eventType or 'UNKNOWN'
            try:
                event_type_data = self._get_event_type_definition(
                    dynatrace_client, str(instance_info.url), event_type
                )
                display_name = event_type_data.get('displayName', event_type)
                severity_level = event_type_data.get('severityLevel', 'INFO')
            except Exception as e:
                self.log.warning(f"Failed to fetch event type {event_type} for event {event.eventId or 'unknown'}: {e}")
                # Use default values if event type fetch fails
                display_name = event_type
                severity_level = 'INFO'

            impact = "Unspecified"
            source = "builtin"
            if event.properties:
                for ppty in event.properties:
                    if ppty.key == 'impactLevel':
                        impact = ppty.value
                    if ppty.key == 'source':
                        source = ppty.value
            if severity_level == 'INFO':
                # Events with a info severity are send as topology events
                if not event.entityId or not event.entityId.entityId:
                    self.log.warning(f"Event {event.eventId or 'unknown'} has no valid entityId, skipping")
                    continue
                entity_id = event.entityId.entityId.id or 'unknown'

                # Skip PROCESS_GROUP_INSTANCE entities if they've caused 404 errors in this run
                entity_type = self._extract_entity_type(entity_id)
                if entity_type == 'PROCESS_GROUP_INSTANCE' and entity_type in problematic_entity_types:
                    self.log.debug(f"Skipping PROCESS_GROUP_INSTANCE entity {entity_id} due to previous 404 errors")
                    continue

                try:
                    entity_data = self._get_entity_definition(
                        dynatrace_client, str(instance_info.url), entity_id
                    )
                    link_to_entity = self.link_to_dynatrace(entity_id, instance_info.url)
                    self._create_topology_event(event, link_to_entity, severity_level, entity_data, impact,
                                                display_name)
                except Exception as e:
                    # Check if this is a 404 error (entity no longer exists)
                    if "404" in str(e) or "not found" in str(e).lower():
                        # Extract entity type from entity_id if possible
                        entity_type = self._extract_entity_type(entity_id)
                        if entity_type not in entity_404_errors:
                            entity_404_errors[entity_type] = 0
                        entity_404_errors[entity_type] += 1
                        # Mark this entity type as problematic for this run
                        problematic_entity_types.add(entity_type)
                    else:
                        # Log non-404 errors as warnings
                        self.log.info(
                            f"Entity {entity_id or 'unknown'} referenced in event {event.eventId or 'unknown'} "
                            f"error: {e}")
                    # Skip this event since the entity is no longer available
                    continue
            elif (event.status or 'UNKNOWN') == 'OPEN':
                # Create health state for other events that are OPEN
                if severity_level in severity_levels_that_maps_to_deviating_health_state:
                    health_value = Health.DEVIATING
                elif severity_level in severity_levels_that_maps_to_critical_health_state:
                    health_value = Health.CRITICAL
                else:
                    health_value = Health.CLEAR
                try:
                    if not event.entityId or not event.entityId.entityId:
                        self.log.warning(
                            f"Event {event.eventId or 'unknown'} has no valid entityId, skipping health state creation")
                        continue

                    entity_id = event.entityId.entityId.id or 'unknown'

                    # Skip PROCESS_GROUP_INSTANCE entities if they've caused 404 errors in this run
                    entity_type = self._extract_entity_type(entity_id)
                    if entity_type == 'PROCESS_GROUP_INSTANCE' and entity_type in problematic_entity_types:
                        self.log.debug(
                            f"Skipping PROCESS_GROUP_INSTANCE entity {entity_id} for health state creation due to "
                            f"previous 404 errors")
                        continue

                    identifier = Identifiers.create_custom_identifier("dynatrace", entity_id)
                    self.health.check_state(
                        check_state_id=entity_id,
                        name='Dynatrace event',
                        health_value=health_value,
                        topology_element_identifier=identifier,
                        message='Event: {} Severity: {} Impact: {} Open Since: {} Source: {}'.format(
                            display_name or 'Unknown Event', severity_level or 'INFO', impact or 'Unspecified',
                            datetime.fromtimestamp(int(event.startTime or 0) / 1000).strftime(
                                "%b %-d, %Y, %H:%M:%S"), source or 'builtin'
                        )
                    )
                except Exception as e:
                    # Extract entity ID using helper method
                    entity_id = self._get_entity_id(event)

                    # Check if this is a 404 error (entity no longer exists)
                    if "404" in str(e) or "not found" in str(e).lower():
                        # Extract entity type from entity_id if possible
                        entity_type = self._extract_entity_type(entity_id)
                        if entity_type not in entity_404_errors:
                            entity_404_errors[entity_type] = 0
                        entity_404_errors[entity_type] += 1
                        # Mark this entity type as problematic for this run
                        problematic_entity_types.add(entity_type)
                    else:
                        # Log non-404 errors as warnings
                        self.log.warning(
                            f"Failed to create health state for event {event.eventId or 'unknown'} with entity "
                            f"{entity_id}: {e}")
                    # Skip this event since we can't create the health state
                    continue

        # Log accumulated 404 errors as INFO messages per entity type
        for entity_type, count in entity_404_errors.items():
            self.log.debug(f"Found {count} events referencing {entity_type} entities that no longer exist")

        self.health.stop_snapshot()
        if events_limit_reached:
            raise EventLimitReachedException(events_limit_reached)

    def _get_event_type_definition(self, dynatrace_client, base_url, event_type):
        """
        Return the event type definition from cache if present, otherwise fetch and cache it.
        """
        if event_type in self._event_type_cache:
            return self._event_type_cache[event_type]

        endpoint = f"{base_url}/api/v2/eventTypes/{event_type}"
        data = dynatrace_client.get_dynatrace_json_response(endpoint, None)
        # Only cache successful responses
        self._event_type_cache[event_type] = data
        return data

    def _get_entity_definition(self, dynatrace_client, base_url, entity_id):
        """
        Return the entity definition from cache if present, otherwise fetch and cache it.
        """
        if not hasattr(self, '_entity_cache'):
            self._entity_cache = {}
        if entity_id in self._entity_cache:
            return self._entity_cache[entity_id]
        endpoint = f"{base_url}/api/v2/entities/{entity_id}"
        data = dynatrace_client.get_dynatrace_json_response(endpoint, None)
        minimal = {"displayName": data.get("displayName")}
        self._entity_cache[entity_id] = minimal
        return minimal

    def _warm_event_type_cache(self, dynatrace_client, base_url, event_types):
        """
        Pre-fetch and cache event type definitions for a set of event types.
        Failures are logged at debug and ignored to avoid blocking processing.
        """
        for et in event_types:
            if et in self._event_type_cache:
                continue
            try:
                endpoint = f"{base_url}/api/v2/eventTypes/{et}"
                data = dynatrace_client.get_dynatrace_json_response(endpoint, None)
                self._event_type_cache[et] = data
            except Exception as e:
                self.log.debug(f"Warming cache for event type {et} failed: {e}")

    def _warm_all_supported_entities(self, dynatrace_client, base_url, relative_time):
        """
        Prefetch and cache displayName for ALL entities of supported types.
        Uses pagination via nextPageKey. Stores only {'displayName'} to minimize memory.
        """
        if not hasattr(self, '_entity_cache'):
            self._entity_cache = {}
        endpoint = dynatrace_client.get_endpoint(base_url, "api/v2/entities")
        for selector in SUPPORTED_ENTITY_TYPES_PARAM_SELECTORS:
            next_key = None
            while True:
                params = {"entitySelector": selector, "from": f"now-{relative_time}"}
                if next_key:
                    params = {"nextPageKey": next_key}
                resp = dynatrace_client.get_dynatrace_json_response(endpoint, params)
                entities = resp.get("entities", []) if isinstance(resp, dict) else (resp or [])
                for ent in entities:
                    ent_id = ent.get("entityId")
                    if ent_id and ent_id not in self._entity_cache:
                        self._entity_cache[ent_id] = {"displayName": ent.get("displayName")}
                next_key = resp.get("nextPageKey") if isinstance(resp, dict) else None
                if not next_key:
                    break

    def _create_topology_event(self, dynatrace_event, link_to_entity, severity_level, entity_data, impact,
                               event_display_name):
        """
        Create an standard or custom event based on the Dynatrace Severity level
        """
        event = {
            "timestamp": int(time.time()),
            "source_type_name": "Dynatrace Events",
            "msg_title": "%s on %s" % (event_display_name or 'Unknown Event',
                                       entity_data.get('displayName', 'Unknown Entity')),
            "msg_text": "%s on %s" % (event_display_name or 'Unknown Event',
                                      entity_data.get('displayName', 'Unknown Entity')),
            "tags": [
                "entityId:%s" % (dynatrace_event.entityId or 'Unknown'),
                "severityLevel:%s" % (severity_level or 'INFO'),
                "eventType:%s" % (dynatrace_event.eventType or 'UNKNOWN'),
                "impactLevel:%s" % (impact or 'Unspecified'),
                "eventStatus:%s" % (dynatrace_event.status or 'UNKNOWN'),
                "startTime:%s" % (dynatrace_event.startTime or 0),
                "endTime:%s" % (dynatrace_event.endTime or 0),
                # "source:%s" % dynatrace_event.source,
                "openSince:%s" % datetime.fromtimestamp((dynatrace_event.startTime or 0) / 1000).strftime(
                    "%b %-d, %Y, %H:%M:%S"),
            ],
            "context": {
                "source_identifier": "source_identifier_value",
                # Extract entity ID for readability
                "element_identifiers": ["urn:%s" % (
                    self._get_entity_id(dynatrace_event))],
                "source": "dynatrace",
                "category": "info_event",
                "data": dynatrace_event.dict() if hasattr(dynatrace_event, 'dict') else {},
                "source_links": [
                    {
                        "title": "my_event_external_link",
                        "url": link_to_entity or "#"
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
        self.log.info(
            "Calling _get_events with from_time=%s",
            instance_info.state.last_processed_event_timestamp,
        )
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
                    try:
                        self.log.debug(f"Processing event: {event}")
                        dynatrace_event = DynatraceEvent(**event)
                        new_events.append(dynatrace_event)
                        events_processed += 1
                        self._check_event_limit_exceeded_condition(instance_info.events_process_limit, events_processed)
                    except EventLimitReachedException:
                        raise
                    except Exception as e:
                        self.log.error(f"Failed to process event {event.get('eventId', 'unknown')}: {e}")
                        self.log.error(f"Event data: {event}")
                        # Skip this event and continue with the next one
                        continue
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
    def _get_entity_id(event):
        """
        Safely extracts the entity ID from a Dynatrace event.
        Returns 'unknown' if any part of the chain is missing.
        :param event: Dynatrace event object
        :return: entity ID or 'unknown'
        """
        if event.entityId and event.entityId.entityId and event.entityId.entityId.id:
            return event.entityId.entityId.id
        return 'unknown'

    @staticmethod
    def _extract_entity_type(entity_id):
        """
        Extracts entity type from entity ID.
        Dynatrace entity IDs typically follow the pattern: TYPE-UNIQUE_ID
        :param entity_id: Dynatrace entity ID
        :return: entity type or 'unknown'
        """
        if not entity_id or entity_id == 'unknown':
            return 'unknown'

        # Try to extract entity type from the entity ID
        # Dynatrace entity IDs typically follow the pattern: TYPE-UNIQUE_ID
        parts = entity_id.split('-', 1)
        if len(parts) > 1:
            return parts[0].upper()
        else:
            return 'unknown'

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
