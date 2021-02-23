# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

from datetime import datetime, timedelta

from requests import Session, Timeout
from schematics import Model
from schematics.types import IntType, URLType, StringType, ListType, BooleanType, ModelType

from stackstate_checks.base import AgentCheck, StackPackInstance
from stackstate_checks.utils.identifiers import Identifiers

VERIFY_HTTPS = True
TIMEOUT_DEFAULT = 10
EVENTS_BOOSTRAP_DAYS_DEFAULT = 5
EVENTS_PROCESS_LIMIT_DEFAULT = 10000


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
            self.stop_snapshot()
            msg = "Dynatrace check processed successfully"
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=instance_info.instance_tags, message=msg)
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
        applications = self._collect_applications(instance_info)
        services = self._collect_services(instance_info)
        processes_groups = self._collect_process_groups(instance_info)
        processes = self._collect_processes(instance_info)
        hosts = self._collect_hosts(instance_info)
        topology = {"application": applications, "service": services, "process-group": processes_groups,
                    "process": processes, "host": hosts}
        # collect topology for each component type
        for comp_type, response in topology.items():
            self._collect_topology(response, comp_type, instance_info)
        end_time = datetime.now()
        time_taken = end_time - start_time
        self.log.info("Time taken to collect the topology is: {} seconds".format(time_taken.total_seconds()))

    def _collect_relations(self, component, externalId):
        """
        Collects relationships from different component-types
        :param component: the component for which relationships need to be extracted and processed
        :param externalId: the component externalId for and from relationship will be created
        :return: None
        """
        outgoing_relations = component.get("fromRelationships", {})
        incoming_relations = component.get("toRelationships", {})
        for relation_type, relation_value in outgoing_relations.items():
            # Ignore `isSiteOf` relation since location components are not processed right now
            if relation_type != "isSiteOf":
                for target_id in relation_value:
                    self.relation(externalId, target_id, relation_type, {})
        for relation_type, relation_value in incoming_relations.items():
            # Ignore `isSiteOf` relation since location components are not processed right now
            if relation_type != "isSiteOf":
                for source_id in relation_value:
                    self.relation(source_id, externalId, relation_type, {})

    def _collect_processes(self, instance_info):
        """
        Collects the response from the Dynatrace Process API endpoint
        """
        endpoint = urljoin(instance_info.url, "api/v1/entity/infrastructure/processes")
        processes = self._get_dynatrace_json_response(instance_info, endpoint)
        return processes

    def _collect_hosts(self, instance_info):
        """
        Collects the response from the Dynatrace Host API endpoint
        """
        endpoint = urljoin(instance_info.url, "api/v1/entity/infrastructure/hosts")
        hosts = self._get_dynatrace_json_response(instance_info, endpoint)
        return hosts

    def _collect_applications(self, instance_info):
        """
        Collects the response from the Dynatrace Application API endpoint
        """
        endpoint = urljoin(instance_info.url, "api/v1/entity/applications")
        applications = self._get_dynatrace_json_response(instance_info, endpoint)
        return applications

    def _collect_process_groups(self, instance_info):
        """
        Collects the response from the Dynatrace Process-Group API endpoint
        """
        endpoint = urljoin(instance_info.url, "api/v1/entity/infrastructure/process-groups")
        process_groups = self._get_dynatrace_json_response(instance_info, endpoint)
        return process_groups

    def _collect_services(self, instance_info):
        """
        Collects the response from the Dynatrace Service API endpoint
        """
        endpoint = urljoin(instance_info.url, "api/v1/entity/services")
        services = self._get_dynatrace_json_response(instance_info, endpoint)
        return services

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
        :return: create the component on stackstate API
        """
        if "error" in response:
            raise DynatraceError(response["error"].get("message"), response["error"].get("code"), component_type)
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
    def _get_dynatrace_json_response(instance_info, endpoint, params={}):
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


class DynatraceError(Exception):
    """
    Exception raised for errors in Dynatrace API endpoint response

    Attributes:
        message         -- explanation of the error response
        code            -- status code of the error response
        component_type  -- Type of the component for which error occured
    """

    def __init__(self, message, code, component_type):
        super(DynatraceError, self).__init__(self.message)
        self.message = message
        self.code = code
        self.component_type = component_type

    def __str__(self):
        return 'Got an unexpected error with status code {0} and message {1} while processing {2} component ' \
               'type'.format(self.code, self.message, self.component_type)
