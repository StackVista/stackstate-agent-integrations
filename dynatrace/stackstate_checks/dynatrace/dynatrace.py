# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time

try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

from datetime import datetime, timedelta

from requests import Session, Timeout
from schematics import Model
from schematics.types import IntType, URLType, StringType, ListType, BooleanType, ModelType, DictType

from stackstate_checks.base import AgentCheck, StackPackInstance
from stackstate_checks.utils.identifiers import Identifiers

VERIFY_HTTPS = True
TIMEOUT_DEFAULT = 10
EVENTS_BOOSTRAP_DAYS_DEFAULT = 5
EVENTS_PROCESS_LIMIT_DEFAULT = 10000

dynatrace_entities_cache = {}

TOPOLOGY_API_ENDPOINTS = {
    "process": "api/v1/entity/infrastructure/processes",
    "host": "api/v1/entity/infrastructure/hosts",
    "application": "api/v1/entity/applications",
    "process-group": "api/v1/entity/infrastructure/process-groups",
    "service": "api/v1/entity/services"
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
    events_boostrap_days = IntType(default=EVENTS_BOOSTRAP_DAYS_DEFAULT)
    events_process_limit = IntType(default=EVENTS_PROCESS_LIMIT_DEFAULT)
    verify = BooleanType(default=VERIFY_HTTPS)
    cert = StringType()
    keyfile = StringType()
    timeout = IntType(default=TIMEOUT_DEFAULT)
    domain = StringType(default='dynatrace')
    environment = StringType(default='production')
    state = ModelType(State)


class DynatraceCheck(AgentCheck):
    INSTANCE_TYPE = "dynatrace"
    SERVICE_CHECK_NAME = "dynatrace"
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
            self.start_snapshot()
            self._process_topology(instance_info)
            self._process_events(instance_info)
            self.stop_snapshot()
            msg = "Dynatrace check processed successfully"
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=instance_info.instance_tags, message=msg)
        except EventLimitReachedException as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.WARNING, tags=instance_info.instance_tags,
                               message=str(e))
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance_info.instance_tags,
                               message=str(e))

    def _process_topology(self, instance_info):
        """
        Collects components and relations for each component type from dynatrace smartscape topology API
        """
        start_time = datetime.now()
        self.log.info("Starting the collection of topology")
        for component_type, path in TOPOLOGY_API_ENDPOINTS.items():
            endpoint = urljoin(instance_info.url, path)
            response = self._get_dynatrace_json_response(instance_info, endpoint)
            self._collect_topology(response, component_type, instance_info)
        end_time = datetime.now()
        time_taken = end_time - start_time
        self.log.info("Collected %d entities.", len(dynatrace_entities_cache))
        self.log.info("Time taken to collect the topology is: {} seconds".format(time_taken.total_seconds()))

    def _collect_relations(self, component, external_id):
        """
        Collects relationships from different component-types
        :param component: the component for which relationships need to be extracted and processed
        :param external_id: the component externalId for and from relationship will be created
        :return: None
        """
        outgoing_relations = component.get("fromRelationships", {})
        incoming_relations = component.get("toRelationships", {})
        for relation_type, relation_value in outgoing_relations.items():
            # Ignore `isSiteOf` relation since location components are not processed right now
            if relation_type != "isSiteOf":
                for target_id in relation_value:
                    self.relation(external_id, target_id, relation_type, {})
        for relation_type, relation_value in incoming_relations.items():
            # Ignore `isSiteOf` relation since location components are not processed right now
            if relation_type != "isSiteOf":
                for source_id in relation_value:
                    self.relation(source_id, external_id, relation_type, {})

    @staticmethod
    def _clean_unsupported_metadata(component):
        """
        Convert the data type to string in case of `boolean` and `float`.
        Currently we get `float` values for `Hosts`
        :param component: metadata with unsupported data types
        :return: metadata with supported data types
        """
        for key in component.keys():
            if type(component[key]) is float:
                component[key] = str(component[key])
            elif type(component[key]) is bool:
                component[key] = str(component[key])
        return component

    @staticmethod
    def _get_host_identifiers(component):
        host_identifiers = []
        if component.get("esxiHostName"):
            host_identifiers.append(Identifiers.create_host_identifier(component.get("esxiHostName")))
        if component.get("oneAgentCustomHostName"):
            host_identifiers.append(Identifiers.create_host_identifier(component.get("oneAgentCustomHostName")))
        if component.get("azureHostNames"):
            host_identifiers.append(Identifiers.create_host_identifier(component.get("azureHostNames")))
        if component.get("publicHostName"):
            host_identifiers.append(Identifiers.create_host_identifier(component.get("publicHostName")))
        if component.get("localHostName"):
            host_identifiers.append(Identifiers.create_host_identifier(component.get("localHostName")))
        host_identifiers.append(Identifiers.create_host_identifier(component.get("displayName")))
        host_identifiers = Identifiers.append_lowercase_identifiers(host_identifiers)
        return host_identifiers

    def _collect_topology(self, response, component_type, instance_info):
        """
        Process each component type and map those with specific data
        :param response: Response of each component type endpoint
        :param component_type: Component type
        :param instance_info: instance configuration
        :return: create the component on stackstate API
        """
        for item in response:
            item = self._clean_unsupported_metadata(item)
            data = dict()
            external_id = item["entityId"]
            identifiers = [Identifiers.create_custom_identifier("dynatrace", external_id)]
            if component_type == "host":
                host_identifiers = self._get_host_identifiers(item)
                identifiers.extend(host_identifiers)
            # derive useful labels and get labels from dynatrace tags
            labels = self._get_labels(item)
            data.update(item)
            self._filter_item_topology_data(data)
            data.update({
                "identifiers": identifiers,
                "tags": instance_info.instance_tags,
                "domain": instance_info.domain,
                "environment": instance_info.environment,
                "instance": instance_info.url,
                "labels": labels
            })
            self.component(external_id, component_type, data)
            self._collect_relations(item, external_id)
            dynatrace_entities_cache[external_id] = {"name": data.get("displayName"), "type": component_type}

    @staticmethod
    def _filter_item_topology_data(data):
        """
        Delete the un-necessary relationships from the data
        """
        if "fromRelationships" in data:
            del data["fromRelationships"]
        if "toRelationships" in data:
            del data["toRelationships"]
        if "tags" in data:
            del data["tags"]

    @staticmethod
    def _get_labels_from_dynatrace_tags(item):
        """
        Process each tag as a label in component
        :param item: the component item to read from
        :return: list of added tags as labels
        """
        tags = []
        for tag in item.get("tags", []):
            tag_label = ''
            if tag.get('context') and tag.get('context') != 'CONTEXTLESS':
                tag_label += "[%s]" % tag['context']
            if tag.get('key'):
                tag_label += tag['key']
            if tag.get('value'):
                tag_label += ":%s" % tag['value']
            tags.append(tag_label)
        return tags

    def _get_labels(self, item):
        """
        Extract labels and tags for each component
        :param item: the component item
        :return: the list of added labels for a component
        """
        labels = []
        # append management zones in labels for each existing component
        for zone in item.get("managementZones", []):
            if zone.get("name"):
                labels.append("managementZones:%s" % zone.get("name"))
        if item.get("entityId"):
            labels.append(item["entityId"])
        if "monitoringState" in item:
            actual_state = item["monitoringState"].get("actualMonitoringState")
            expected_state = item["monitoringState"].get("expectedMonitoringState")
            if actual_state:
                labels.append("actualMonitoringState:%s" % actual_state)
            if expected_state:
                labels.append("expectedMonitoringState:%s" % expected_state)
        for technologies in item.get("softwareTechnologies", []):
            tech_label = ''
            if technologies.get('type'):
                tech_label += technologies['type']
            if technologies.get('edition'):
                tech_label += ":%s" % technologies['edition']
            if technologies.get('version'):
                tech_label += ":%s" % technologies['version']
            labels.append(tech_label)
        labels_from_tags = self._get_labels_from_dynatrace_tags(item)
        labels.extend(labels_from_tags)
        # prefix the labels with `dynatrace-` for all labels
        labels = ["dynatrace-%s" % label for label in labels]
        return labels

    def _process_events(self, instance_info):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        entities_with_events = []
        events, events_limit_reached = self._collect_events(instance_info)
        closed_events = len([e for e in events if e.get('eventStatus') == 'CLOSED'])
        open_events = len([e for e in events if e.get('eventStatus') == 'OPEN'])
        self.log.info("Collected %d events, %d are open and %d are closed.", len(events), open_events, closed_events)
        for event in events:
            self._create_event(event, instance_info.url)
            entities_with_events.append(event.entityId)
        # Simulating OK health state by sending CLOSED events for processed topology entities with no events.
        simulated_count = 0
        for entity_id in [e for e in dynatrace_entities_cache.keys() if e not in entities_with_events]:
            simulated_closed_event = DynatraceEvent(
                {
                    "eventId": -1,
                    "startTime": self._current_time_seconds() * 1000,
                    "endTime": self._current_time_seconds() * 1000,
                    "entityId": entity_id,
                    "entityName": dynatrace_entities_cache[entity_id].get('name'),
                    "impactLevel": None,
                    "eventType": "CUSTOM_ALERT",
                    "eventStatus": "OK STATUS",
                    "tags": [],
                    "id": -1,
                    "source": "StackState Agent"
                }
            )
            self._create_event(simulated_closed_event, instance_info.url)
            simulated_count += 1
        self.log.info("Created %d events and %d simulated closed events.", len(entities_with_events), simulated_count)
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
        events = self._get_dynatrace_json_response(instance_info, endpoint, params)
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

    def _generate_bootstrap_timestamp(self, days):
        """
        Creates timestamp n days in the past from the current moment. It is used in tests too.
        :param days: how many days in the past
        :return:
        """
        bootstrap_date = datetime.fromtimestamp(self._current_time_seconds()) - timedelta(days=days)
        return int(bootstrap_date.strftime('%s')) * 1000

    @staticmethod
    def _current_time_seconds():
        """
        This method is mocked for testing. Do not change its behavior
        :return: current timestamp
        """
        return int(time.time())

    def _get_dynatrace_json_response(self, instance_info, endpoint, params=None):
        headers = {"Authorization": "Api-Token {}".format(instance_info.token)}
        try:
            with Session() as session:
                session.headers.update(headers)
                session.verify = instance_info.verify
                if instance_info.cert:
                    session.cert = (instance_info.cert, instance_info.keyfile)
                response = session.get(endpoint, params=params)
                response_json = response.json()
                if response.status_code != 200:
                    if "error" in response_json:
                        msg = response_json["error"].get("message")
                    else:
                        msg = "Got %s when hitting %s" % (response.status_code, endpoint)
                    self.log.error(msg)
                    raise Exception(
                        'Got an unexpected error with status code {0} and message: {1}'.format(response.status_code,
                                                                                               msg))
                return response_json
        except Timeout:
            msg = "{} seconds timeout".format(instance_info.timeout)
            raise Exception("Timeout exception occurred for endpoint {0} with message: {1}".format(endpoint, msg))


class EventLimitReachedException(Exception):
    """
    Exception raised when maximum number of event reached
    """
    pass
