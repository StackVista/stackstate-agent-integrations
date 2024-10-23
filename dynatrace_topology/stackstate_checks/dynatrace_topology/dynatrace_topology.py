# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from collections import namedtuple
from datetime import datetime

from schematics import Model
from schematics.types import IntType, URLType, StringType, ListType, BooleanType, ModelType, DictType

from stackstate_checks.base import AgentCheck, StackPackInstance, HealthStream, HealthStreamUrn, Health
from stackstate_checks.dynatrace.dynatrace_client import DynatraceClient
from stackstate_checks.utils.identifiers import Identifiers

from stackstate_checks.dynatrace_topology.entity_data_types import ApplicationEntity, HostEntity, QueueEntity, ServiceEntity, ProcessGroupEntity, ProcessGroupInstanceEntity, CustomDeviceEntity

VERIFY_HTTPS = True
TIMEOUT = 10
RELATIVE_TIME = 'hour'
ENVIRONMENT = 'production'
DOMAIN = 'dynatrace'

API_V2_DEFAULT_RELATIVE_TIME = '1h'
API_V2_DEFAULT_FIELDS_STRING = '+fromRelationships,+toRelationships,+tags,+managementZones,+properties'

TOPOLOGY_API_SPEC = {
    "process": ("api/v2/entities", 'type("PROCESS_GROUP_INSTANCE")', f'{API_V2_DEFAULT_FIELDS_STRING}'),
    "host": ("api/v2/entities", 'type("HOST")', f'{API_V2_DEFAULT_FIELDS_STRING}'),
    "application": ("api/v2/entities", 'type("APPLICATION")', f'{API_V2_DEFAULT_FIELDS_STRING}'),
    "process-group": ("api/v2/entities", 'type("PROCESS_GROUP")', f'{API_V2_DEFAULT_FIELDS_STRING}'),
    "service": ("api/v2/entities", 'type("SERVICE")', f'{API_V2_DEFAULT_FIELDS_STRING}'),
    "custom-device": ("api/v2/entities", 'type("CUSTOM_DEVICE")', f'{API_V2_DEFAULT_FIELDS_STRING}'),
    "synthetic-monitor": ("api/v1/synthetic/monitors", None, None),
    "queue": ("api/v2/entities", 'type("QUEUE")', f'{API_V2_DEFAULT_FIELDS_STRING}'),
}

DynatraceCachedEntity = namedtuple('DynatraceCachedEntity', 'identifier external_id name type')

class Entity(Model):
    entityId = StringType(required=True)
    displayName = StringType(required=True)
    fromRelationships = DictType(ListType(DictType(StringType)), default={})
    managementZones = ListType(DictType(StringType), default={})
    properties = DictType(StringType, default={})
    tags = ListType(DictType(StringType), default=[])
    toRelationships = DictType(ListType(DictType(StringType)), default={})
    type = StringType(required=True)

class ApiV2EntitiesResponse(Model):
    entities = ListType(ModelType(Entity))
    nextPageKey = StringType()
    pageSize = IntType()
    totalCount = IntType()

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
    azureHostNames = ListType(StringType(), default=[])
    publicHostName = StringType()
    localHostName = StringType()


class InstanceInfo(Model):
    url = URLType(required=True)
    token = StringType(required=True)
    instance_tags = ListType(StringType, default=[])
    verify = BooleanType(default=VERIFY_HTTPS)
    cert = StringType()
    keyfile = StringType()
    timeout = IntType(default=TIMEOUT)
    domain = StringType(default=DOMAIN)
    environment = StringType(default=ENVIRONMENT)
    relative_time = StringType(default=RELATIVE_TIME)
    custom_device_fields = StringType(default=API_V2_DEFAULT_FIELDS_STRING)
    custom_device_relative_time = StringType(default=API_V2_DEFAULT_FIELDS_STRING)
    custom_device_ip = BooleanType(default=True)


class DynatraceTopologyCheck(AgentCheck):
    INSTANCE_TYPE = "dynatrace"
    SERVICE_CHECK_NAME = "dynatrace-topology"
    INSTANCE_SCHEMA = InstanceInfo

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.dynatrace_entities_cache = None

    def get_instance_key(self, instance_info):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance_info.url))

    def get_health_stream(self, instance):
        return HealthStream(HealthStreamUrn(self.INSTANCE_TYPE, "dynatrace-monitored"))

    def check(self, instance_info):
        self.dynatrace_entities_cache = []
        try:
            dynatrace_client = DynatraceClient(instance_info.token,
                                               instance_info.verify,
                                               instance_info.cert,
                                               instance_info.keyfile,
                                               instance_info.timeout)
            # topology snapshot
            self._process_topology(dynatrace_client, instance_info)
            # monitored health snapshot
            self.monitored_health()
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

    @staticmethod
    def get_entity_params(custom_device_relative_time, entity_type_fields, component_type, next_page_key=None):
        """
        Process the default parameters needed for custom device
        @param
        instance_info: Instance configuration schema
        next_page_key: nextPageKey value for pagination of API results
        @return
        Returns the parameter for custom device entities
        """
        if next_page_key:
            params = {'nextPageKey': next_page_key}
        else:
            params = {'entitySelector': TOPOLOGY_API_SPEC[component_type][1]}
            relative_time = {'from': 'now-{}'.format(custom_device_relative_time)}
            params.update(relative_time)
            fields = {'fields': '{}'.format(entity_type_fields)}
            params.update(fields)
        return params

    def collect_entities_get_next_key(self, dynatrace_client, instance_info, endpoint, component_type,
                                      entity_type_fields, next_page_key=None):
        """
        Process custom device response & topology and returns the next page key for result
        @param
        instance_info: Instance configuration schema
        endpoint: Endpoint to collect custom devices
        component_type: Type of the component
        next_page_key: nextPageKey value for pagination of API results
        @return
        Returns the next_page_key value from API response
        """
        params = self.get_entity_params(instance_info.relative_time,
                                        entity_type_fields,
                                        component_type,
                                        next_page_key)
        response = dynatrace_client.get_dynatrace_json_response(endpoint, params)
        self._collect_topology(response.get("entities", []), component_type, instance_info)
        return response.get('nextPageKey')

    def process_entity_topology(self, dynatrace_client, instance_info, endpoint, component_type, entity_type_fields):
        """
        Process the custom device topology until next page key is None
        @param
        instance_info: Instance configuration schema
        endpoint: Endpoint to collect custom devices
        component_type: Type of the component
        @return
        None
        """
        next_page_key = self.collect_entities_get_next_key(dynatrace_client, instance_info, endpoint,
                                                           component_type, entity_type_fields)
        while next_page_key:
            next_page_key = self.collect_entities_get_next_key(dynatrace_client, instance_info, endpoint,
                                                               component_type,
                                                               entity_type_fields,
                                                               next_page_key)

    def _process_topology(self, dynatrace_client, instance_info):
        """
        Collects components and relations for each component type from dynatrace smartscape topology API
        and custom devices from Entities API (v2)
        """
        self.start_snapshot()
        start_time = datetime.now()
        self.log.debug("Starting the collection of topology")
        for component_type, data_tuple in TOPOLOGY_API_SPEC.items():
            endpoint = dynatrace_client.get_endpoint(instance_info.url, data_tuple[0])
            if component_type != "synthetic-monitor":
                # process the custom device topology separately because of pagination
                self.process_entity_topology(dynatrace_client, instance_info, endpoint, component_type, data_tuple[2])
            else:
                params = {"relativeTime": instance_info.relative_time}
                response = dynatrace_client.get_dynatrace_json_response(endpoint, params)
                if component_type == "synthetic-monitor":
                    self.log.debug("Starting the collection of synthetics")
                    for monitor in response.get('monitors', []):
                        monitor.update({"displayName": monitor["name"]})
                        if monitor.get("tags") is None:
                            monitor.update({"tags": []})
                    self.log.debug("Monitors collected : %s" % response.get('monitors', []))
                    self._collect_topology(response.get('monitors', []), component_type, instance_info)
                else:
                    self._collect_topology(response, component_type, instance_info)
        end_time = datetime.now()
        time_taken = end_time - start_time
        self.log.info("Collected %d topology entities.", len(self.dynatrace_entities_cache))
        self.log.debug("Time taken to collect the topology is: %d seconds" % time_taken.total_seconds())
        self.stop_snapshot()

    @staticmethod
    def process_custom_device_identifiers(custom_device, create_identifier_based_on_custom_device_ip):
        """
        Process identifiers for custom devices based on ip address and dns names
        @param
        custom_device: Custom Device element from Dynatrace
        @param
       send_custom_device_ip: Custom devices can have same IP. Disable identifier generation based on IP address.
        @return
        Return the set of identifiers
        """
        properties = custom_device.get("properties")
        identifiers = []
        if properties:
            for dns in properties.get('dnsNames', []):
                identifiers.append(Identifiers.create_host_identifier(dns))
            if create_identifier_based_on_custom_device_ip:
                for ip in properties.get('ipAddress', []):
                    identifiers.append(Identifiers.create_host_identifier(ip))
        return identifiers

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
            try:
                if component_type != "synthetic-monitor":
                    if component_type == "host":
                        dynatrace_component = HostEntity(item, strict=False)
                    elif component_type == "service":
                        dynatrace_component = ServiceEntity(item, strict=False)
                    elif component_type == "queue":
                        dynatrace_component = QueueEntity(item, strict=False)
                    elif component_type == "process-group":
                        dynatrace_component = ProcessGroupEntity(item, strict=False)
                    elif component_type == "process":
                        dynatrace_component = ProcessGroupInstanceEntity(item, strict=False)
                    elif component_type == "application":
                        dynatrace_component = ApplicationEntity(item, strict=False)
                    elif component_type == "custom-device":
                        dynatrace_component = CustomDeviceEntity(item, strict=False)
                    else:
                        dynatrace_component = Entity(item, strict=False)
                else:
                    dynatrace_component = DynatraceComponent(item, strict=False)
            except Exception as e:
                self.log.warn("Couldn't create topology component: %s" % e)
                print(f"{item}")
                raise e

            try:
                dynatrace_component.validate()
            except Exception as e:
                self.log.warn("Couldn't validate topology component: %s" % e)
                continue

            data = {}
            external_id = dynatrace_component.entityId
            identifiers = [Identifiers.create_custom_identifier("dynatrace", external_id)]
            self.dynatrace_entities_cache.append(
                DynatraceCachedEntity(identifiers[0], external_id, dynatrace_component.displayName, component_type)
            )
            if component_type == "host":
                host_identifiers = self._get_host_identifiers(dynatrace_component)
                identifiers.extend(host_identifiers)
            if component_type == "custom-device":
                custom_device_identifiers = self.process_custom_device_identifiers(item,
                                                                                   instance_info.custom_device_ip)
                identifiers.extend(custom_device_identifiers)
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
            self._collect_relations(dynatrace_component, external_id, component_type)

    def _set_relations(self, relationship_items, component_id, component_type, is_target_component):
        """
        Sets relationships for different component-types
        :param relationship_items: the component for which relationships need to be extracted and processed
        :param component_id: the component externalId the for and from relationship will be created
        :param component_type: the component type
        :param is_target_component: boolean indicating the diretion of the relationship
        :return: None
        """
        for relation_type, relation_value in relationship_items:
            # Ignore `isSiteOf` relation since location components are not processed right now
            if relation_type != "isSiteOf":
                for relation_id in relation_value:
                    # Sets the source_id and target_id of the StackState relation depending on if
                    # it is a incoming or outgoing relationship
                    source_id = relation_id if is_target_component else component_id
                    target_id = component_id if is_target_component else relation_id

                    # special case for api v1 because v2 relation values will be a dictionaries at this point
                    if component_type != 'synthetic-monitor':
                        entity_id = relation_id.get('id')
                        if is_target_component:
                            self.relation(entity_id, component_id, relation_type, {})
                        else:
                            self.relation(component_id, entity_id, relation_type, {})
                    elif relation_type == 'monitors':
                        self.relation(target_id, source_id, relation_type, {})
                    else:
                        self.relation(source_id, target_id, relation_type, {})

    def _collect_relations(self, dynatrace_component, external_id, component_type):
        """
        Collects relationships from different component-types
        :param dynatrace_component: the component for which relationships need to be extracted and processed
        :param external_id: the component externalId for and from relationship will be created
        :param component_type: the component type
        :return: None
        """
        # A note on Dynatrace relations terminology:
        # dynatrace_component.fromRelationships are 'outgoing relations', thus 'source components' in StackState
        # dynatrace_component.toRelationships are 'incoming relations', thus 'target components' in StackState
        self._set_relations(dynatrace_component.fromRelationships.items(), external_id, component_type,
                            is_target_component=False)
        self._set_relations(dynatrace_component.toRelationships.items(), external_id, component_type,
                            is_target_component=True)

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
            elif type(component[key]) is int:
                component[key] = str(component[key])
                self.log.debug('Converting %s from int to str.' % key)
        if "lastSeenTimestamp" in component:
            del component["lastSeenTimestamp"]
        return component

    @staticmethod
    def _get_host_identifiers(component):
        host_identifiers = []

        properties = component.properties

        if properties:
            if properties.get("azureHostNames"):
                for azure_host_name in properties.get("azureHostNames"):
                    host_identifiers.append(Identifiers.create_host_identifier(azure_host_name))
            if properties.get("oneAgentCustomHostName"):
                host_identifiers.append(Identifiers.create_host_identifier(properties.get("oneAgentCustomHostName")))
            if properties.get("ipAddress"):
                for ip in properties.get("ipAddress"):
                    host_identifiers.append(Identifiers.create_host_identifier(ip))
            # if properties.get("detectedName"):
            #     host_identifiers.append(Identifiers.create_host_identifier(properties.get("detectedName")))
            if properties.get("dnsNames"):
                for dns in properties.get("dnsNames"):
                    host_identifiers.append(Identifiers.create_host_identifier(dns))
            if properties.get("gceHostName"):
                host_identifiers.append(Identifiers.create_host_identifier(properties.get("gceHostName")))
            # if properties.get("esxiHostName"):
            #     host_identifiers.append(Identifiers.create_host_identifier(properties.get("esxiHostName")))
            # if properties.get("hypervisorType"):
            #     host_identifiers.append(Identifiers.create_host_identifier(properties.get("hypervisorType")))

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
        # Check if dynatrace_component is an instance of DynatraceComponent or Entity
        if isinstance(dynatrace_component, DynatraceComponent):
            if dynatrace_component.get('monitoringState'):
                if dynatrace_component.monitoringState.actualMonitoringState:
                    labels.append(
                        "actualMonitoringState:%s" % dynatrace_component.monitoringState.actualMonitoringState)
                if dynatrace_component.monitoringState.expectedMonitoringState:
                    labels.append(
                        "expectedMonitoringState:%s" % dynatrace_component.monitoringState.expectedMonitoringState)

            # append management zones in labels for each existing component
            for zone in dynatrace_component.managementZones:
                if zone.get("name"):
                    labels.append("managementZones:%s" % zone.get("name"))
            if dynatrace_component.entityId:
                labels.append(dynatrace_component.entityId)

            if dynatrace_component.get('softwareTechnologies'):
                for technologies in dynatrace_component.softwareTechnologies:
                    tech_label = ':'.join(filter(None, [technologies.get('type'), technologies.get('edition'),
                                          technologies.get('version')]))
                    labels.append(tech_label)
            labels_from_tags = self._get_labels_from_dynatrace_tags(dynatrace_component)
            labels.extend(labels_from_tags)
        else:
            # If dynatrace_component is not an instance of DynatraceComponent, it should be an instance of Entity
            if dynatrace_component.entityId:
                labels.append(dynatrace_component.entityId)
            if dynatrace_component.properties:
                # What would previously have been fields of DynatraceComponent are now properties of Entity
                # append what would have been from DynatraceComponent, but now from Entity
                for prop in dynatrace_component.properties:
                    if type(prop) is dict:
                        labels = self._process_labels(labels, prop)
                    elif type(prop) is list:
                        for item in prop:
                            if type(item) is dict:
                                labels = self._process_labels(labels, item)
        return labels


    @staticmethod
    def _process_labels(labels_in, dynatrace_component_property_dict):
        """
        Process labels from DynatraceComponent properties
        :param labels_in: list of labels
        :param dynatrace_component_property_dict: dictionary of DynatraceComponent properties
        :return:
        """
        labels_out = labels_in
        if dynatrace_component_property_dict.get("monitoringState"):
            labels_out.append("monitoringState:%s" % dynatrace_component_property_dict.get("monitoringState"))
            monitoring_state = dynatrace_component_property_dict.get("value")
            if monitoring_state.get("actualMonitoringState"):
                labels_out.append("actualMonitoringState:%s" % monitoring_state.get("actualMonitoringState"))
            if monitoring_state.get("expectedMonitoringState"):
                labels_out.append("expectedMonitoringState:%s" % monitoring_state.get("expectedMonitoringState"))
        elif dynatrace_component_property_dict.get("key") == "managementZones":
            labels_out.append("managementZones:%s" % dynatrace_component_property_dict.get("value"))
        elif dynatrace_component_property_dict.get("key") == "softwareTechnologies":
            sp_type = "undefined"
            sp_version = "undefined"
            sp_edition = "undefined"
            if dynatrace_component_property_dict.get("type"):
                sp_type = dynatrace_component_property_dict.get("type")
            if dynatrace_component_property_dict.get("version"):
                sp_version = dynatrace_component_property_dict.get("version")
            if dynatrace_component_property_dict.get("edition"):
                sp_edition = dynatrace_component_property_dict.get("edition")
            tech_label = ':'.join(filter(None, [technologies.get('type'), technologies.get('edition'),
                                                technologies.get('version')]))
            labels_out.append(tech_label)
        return labels_out

    def monitored_health(self):
        """
        Generates health snapshot with Dynatrace monitored CLEAR health state for all components.
        :return: None
        """
        self.health.start_snapshot()
        for entity in self.dynatrace_entities_cache:
            self.health.check_state(
                check_state_id=entity.external_id,
                name='Dynatrace monitored',
                health_value=Health.CLEAR,
                topology_element_identifier=entity.identifier,
                message='{} is monitored by Dynatrace'.format(entity.name)
            )
        self.health.stop_snapshot()


class EventLimitReachedException(Exception):
    """
    Exception raised when maximum number of event reached
    """
    pass
