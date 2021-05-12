# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time
from datetime import datetime, timedelta

from requests import Session, Timeout
from schematics import Model
from schematics.types import IntType, URLType, StringType, ListType, BooleanType, ModelType, DictType

from stackstate_checks.base import AgentCheck, StackPackInstance
from stackstate_checks.utils.identifiers import Identifiers

# Default values
VERIFY_HTTPS = True
TIMEOUT = 10
EVENTS_BOOSTRAP_DAYS = 5
EVENTS_PROCESS_LIMIT = 10000
RELATIVE_TIME = 'hour'
ENVIRONMENT = 'production'
DOMAIN = 'dynatrace'

TOPOLOGY_API_ENDPOINTS = {
    "process": "api/v1/entity/infrastructure/processes",
    "host": "api/v1/entity/infrastructure/hosts",
    "application": "api/v1/entity/applications",
    "process-group": "api/v1/entity/infrastructure/process-groups",
    "service": "api/v1/entity/services"
}

SYNTHETICS_API_ENDPOINTS = {
    "monitor": "api/v1/synthetic/monitors",
}

DYNATRACE_UI_URLS = {
    "service": "%s/#newservices/serviceOverview;id=%s",
    "process-group": "%s/#processgroupdetails;id=%s",
    "process": "%s/#processdetails;id=%s",
    "host": "%s/#newhosts/hostdetails;id=%s",
    "application": "%s/#uemapplications/uemappmetrics;uemapplicationId=%s"
}

dynatrace_entities_cache = {}


class MonitoringState(Model):
    actualMonitoringState = StringType()
    expectedMonitoringState = StringType()
    restartRequired = BooleanType()


class DynatraceComponent(Model):
    # Common fields to Host, Process, Process groups, Services and Applications
    entityId = StringType(required=True)
    displayName = StringType(required=True)
    customizedName = StringType()
    discoveredName = StringType()
    firstSeenTimestamp = IntType()
    lastSeenTimestamp = IntType()
    tags = ListType(DictType(StringType))
    fromRelationships = DictType(ListType(StringType), default={})
    toRelationships = DictType(ListType(StringType), default={})
    managementZones = ListType(DictType(StringType), default=[])
    # Host, Process, Process groups, Services
    softwareTechnologies = ListType(DictType(StringType), default=[])
    # Process
    monitoringState = ModelType(MonitoringState)
    # Host
    esxiHostName = StringType()
    oneAgentCustomHostName = StringType()
    azureHostNames = StringType()
    publicHostName = StringType()
    localHostName = StringType()


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
    domain = StringType(default=DOMAIN)
    environment = StringType(default=ENVIRONMENT)
    relative_time = StringType(default=RELATIVE_TIME)
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
            self._process_synthetics(instance_info)
            self.stop_snapshot()
            # process events is not inside snapshot block as Vishal suggested
            self._process_events(instance_info)
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
        self.log.debug("Starting the collection of topology")
        for component_type, path in TOPOLOGY_API_ENDPOINTS.items():
            endpoint = self._get_endpoint(instance_info.url, path)
            params = {"relativeTime": instance_info.relative_time}
            response = self._get_dynatrace_json_response(instance_info, endpoint, params)
            self._collect_topology(response, component_type, instance_info)
        end_time = datetime.now()
        time_taken = end_time - start_time
        self.log.info("Collected %d topology entities.", len(dynatrace_entities_cache))
        self.log.debug("Time taken to collect the topology is: %d seconds" % time_taken.total_seconds())

    def _process_synthetics(self, instance_info):
        """
        Collects the synthetic checks from dynatrace API
        """
        start_time = datetime.now()
        self.log.debug("Starting the collection of synthetics")
        for component_type, path in SYNTHETICS_API_ENDPOINTS.items():
            endpoint = self._get_endpoint(instance_info.url, path)
            params = {"relativeTime": instance_info.relative_time}
            response = self._get_dynatrace_json_response(instance_info, endpoint, params)
            for monitor in response["monitors"]:
                monitor = self._get_dynatrace_json_response(instance_info, endpoint + "/" +monitor["entityId"])
                self._collect_monitors(monitor, component_type, instance_info)
        end_time = datetime.now()
        time_taken = end_time - start_time 
        self.log.debug("Time taken to collect the synthetics is: %d seconds" % time_taken.total_seconds()) 

    def _collect_monitors(self, monitor, component_type, instance_info):
        monitor = self._clean_unsupported_metadata(monitor)
        monitor.update({"displayName": monitor["name"]})
        dynatrace_component = DynatraceComponent(monitor, strict=False)
        #dynatrace_component.validate()
        data = {}
        external_id = dynatrace_component.entityId
        identifiers = [Identifiers.create_custom_identifier("dynatrace", external_id)]
        if component_type == "host":
            host_identifiers = self._get_host_identifiers(dynatrace_component)
            identifiers.extend(host_identifiers)
        # derive useful labels from dynatrace tags
        tags = self._get_labels(dynatrace_component)
        tags.extend(instance_info.instance_tags)
        data.update(monitor)
        self._filter_item_topology_data(data)
        data.update({
            "identifiers": identifiers,
            "tags": tags,
            "domain": instance_info.domain,
            "environments": [instance_info.environment],
            "instance": instance_info.url,
        })
        self.component(external_id, component_type, data)
        dynatrace_entities_cache[external_id] = {"name": dynatrace_component.displayName, "type": component_type}
        

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
            dynatrace_component = DynatraceComponent(item, strict=False)
            dynatrace_component.validate()
            data = {}
            external_id = dynatrace_component.entityId
            identifiers = [Identifiers.create_custom_identifier("dynatrace", external_id)]
            if component_type == "host":
                host_identifiers = self._get_host_identifiers(dynatrace_component)
                identifiers.extend(host_identifiers)
            # derive useful labels from dynatrace tags
            tags = self._get_labels(dynatrace_component)
            tags.extend(instance_info.instance_tags)
            data.update(item)
            self._filter_item_topology_data(data)
            data.update({
                "identifiers": identifiers,
                "tags": tags,
                "domain": instance_info.domain,
                "environments": [instance_info.environment],
                "instance": instance_info.url,
            })
            self.component(external_id, component_type, data)
            self._collect_relations(dynatrace_component, external_id)
            dynatrace_entities_cache[external_id] = {"name": dynatrace_component.displayName, "type": component_type}

    def _collect_relations(self, dynatrace_component, external_id):
        """
        Collects relationships from different component-types
        :param dynatrace_component: the component for which relationships need to be extracted and processed
        :param external_id: the component externalId for and from relationship will be created
        :return: None
        """
        # A note on Dynatrace relations terminology:
        # dynatrace_component.fromRelationships are 'outgoing relations'
        # dynatrace_component.toRelationships are 'incoming relations'
        for relation_type, relation_value in dynatrace_component.fromRelationships.items():
            # Ignore `isSiteOf` relation since location components are not processed right now
            if relation_type != "isSiteOf":
                for target_id in relation_value:
                    self.relation(external_id, target_id, relation_type, {})
        for relation_type, relation_value in dynatrace_component.toRelationships.items():
            # Check if relationship type is monitors, since monitors has an inverted relationship
            if relation_type == "monitors":
                for source_id in relation_value:
                    self.relation(external_id, source_id, relation_type, {})
                # we need to continue to prevent processing the monitor again with the inverted relationship.
                continue
            # Ignore `isSiteOf` relation since location components are not processed right now
            if relation_type != "isSiteOf":
                for source_id in relation_value:
                    self.relation(source_id, external_id, relation_type, {})

    def _clean_unsupported_metadata(self, component):
        """
        Convert the data type to string in case of `boolean` and `float`.
        Currently we get `float` values for `Hosts`
        :param component: metadata with unsupported data types
        :return: metadata with supported data types
        """
        for key in component.keys():
            if type(component[key]) is float:
                component[key] = str(component[key])
                self.log.debug('Converting %s from float to str.' % key)
            elif type(component[key]) is bool:
                component[key] = str(component[key])
                self.log.debug('Converting %s from bool to str.' % key)
        return component

    @staticmethod
    def _get_host_identifiers(component):
        host_identifiers = []
        if component.esxiHostName:
            host_identifiers.append(Identifiers.create_host_identifier(component.esxiHostName))
        if component.oneAgentCustomHostName:
            host_identifiers.append(Identifiers.create_host_identifier(component.oneAgentCustomHostName))
        if component.azureHostNames:
            host_identifiers.append(Identifiers.create_host_identifier(component.azureHostNames))
        if component.publicHostName:
            host_identifiers.append(Identifiers.create_host_identifier(component.publicHostName))
        if component.localHostName:
            host_identifiers.append(Identifiers.create_host_identifier(component.localHostName))
        host_identifiers.append(Identifiers.create_host_identifier(component.displayName))
        host_identifiers = Identifiers.append_lowercase_identifiers(host_identifiers)
        return host_identifiers

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
    def _get_labels_from_dynatrace_tags(dynatrace_component):
        """
        Process each tag as a label in component
        :param dynatrace_component: the component item to read from
        :return: list of added tags as labels
        """
        tags = []
        for tag in dynatrace_component.tags:
            tag_label = ''
            if tag.get('context') and tag.get('context') != 'CONTEXTLESS':
                tag_label += "[%s]" % tag['context']
            if tag.get('key'):
                tag_label += tag['key']
            if tag.get('value'):
                tag_label += ":%s" % tag['value']
            tags.append(tag_label)
        return tags

    def _get_labels(self, dynatrace_component):
        """
        Extract labels and tags for each component
        :param dynatrace_component: the component item
        :return: the list of added labels for a component
        """
        labels = []
        # append management zones in labels for each existing component
        for zone in dynatrace_component.managementZones:
            if zone.get("name"):
                labels.append("managementZones:%s" % zone.get("name"))
        if dynatrace_component.entityId:
            labels.append(dynatrace_component.entityId)
        if dynatrace_component.monitoringState:
            if dynatrace_component.monitoringState.actualMonitoringState:
                labels.append("actualMonitoringState:%s" % dynatrace_component.monitoringState.actualMonitoringState)
            if dynatrace_component.monitoringState.expectedMonitoringState:
                labels.append(
                    "expectedMonitoringState:%s" % dynatrace_component.monitoringState.expectedMonitoringState)
        for technologies in dynatrace_component.softwareTechnologies:
            tech_label = ''
            if technologies.get('type'):
                tech_label += technologies['type']
            if technologies.get('edition'):
                tech_label += ":%s" % technologies['edition']
            if technologies.get('version'):
                tech_label += ":%s" % technologies['version']
            labels.append(tech_label)
        labels_from_tags = self._get_labels_from_dynatrace_tags(dynatrace_component)
        labels.extend(labels_from_tags)
        return labels

    def _process_events(self, instance_info):
        """
        Wrapper to collect events, filters those events and persist the state
        """
        entities_with_events = []
        events, events_limit_reached = self._collect_events(instance_info)
        open_events = len([e for e in events if e.get('eventStatus') == 'OPEN'])
        closed_events = len(events) - open_events
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
                    "eventType": "DEFAULT HEALTH",
                    "eventStatus": "OK",
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
                "openSince:%s" % self._timestamp_to_sts_datetime(dynatrace_event),
            ]
        }

        # Events with a info severity are send as custom events
        if dynatrace_event.severityLevel == 'INFO':
            event["context"] = {
                "source_identifier": "source_identifier_value",
                "element_identifiers": ["urn:%s" % dynatrace_event.entityId],
                "source": "dynatrace",
                "category": "info_event",
                "data": dynatrace_event.to_primitive(),
                "source_links": [
                    {
                        "title": "my_event_external_link",
                        "url": self._link_to_dynatrace(dynatrace_event.entityId, instance_url)
                    }
                ]
            }

        self.event(event)

    @staticmethod
    def _timestamp_to_sts_datetime(dynatrace_event):
        return datetime.fromtimestamp(dynatrace_event.startTime / 1000).strftime("%b %-d, %Y, %H:%M:%S")

    @staticmethod
    def _link_to_dynatrace(entity_id, instance_url):
        entity = dynatrace_entities_cache.get(entity_id)
        if entity:
            return DYNATRACE_UI_URLS[entity["type"]] % (instance_url, entity_id)
        else:
            return instance_url

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
            raise EventLimitReachedException("Maximum event limit to process is %s but received total %s events"
                                             % (instance_info.events_process_limit, total_event_count))

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

    def _get_endpoint(self, url, path):
        """
        Creates the API endpoint from the path
        :param url: the URL from conf.yaml
        :param path: the rest of the path of the specific dynatrace endpoint
        :return: the full url of the endpoint
        """
        sanitized_url = url[:-1] if url.endswith("/") else url
        sanitized_path = path[1:] if path.startswith("/") else path
        endpoint = sanitized_url + "/" + sanitized_path
        self.log.debug("Dynatrace URL endpoint %s", endpoint)
        return endpoint

    def _get_dynatrace_json_response(self, instance_info, endpoint, params=None):
        headers = {"Authorization": "Api-Token %s" % instance_info.token}
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
                        'Got an unexpected error with status code %s and message: %s' % (response.status_code, msg))
                return response_json
        except Timeout:
            msg = "%d seconds timeout" % instance_info.timeout
            raise Exception("Timeout exception occurred for endpoint %s with message: %s" % (endpoint, msg))


class EventLimitReachedException(Exception):
    """
    Exception raised when maximum number of event reached
    """
    pass
