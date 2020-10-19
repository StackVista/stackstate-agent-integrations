# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance
from .dynatrace_exception import DynatraceError

import requests
from requests import Session
import yaml
from datetime import datetime


class DynatraceTopologyCheck(AgentCheck):

    INSTANCE_TYPE = "dynatrace"
    SERVICE_CHECK_NAME = "dynatrace"

    def __init__(self, name, init_config, instances=None):
        AgentCheck.__init__(self, name, init_config, instances)
        self.url = None
        self.token = None
        self.tags = []
        self.environment = None
        self.domain = None
        self.verify = None
        self.cert = None
        self.keyfile = None

    def get_instance_key(self, instance):
        if 'url' not in instance:
            raise ConfigurationError('Missing url in configuration.')

        return TopologyInstance(self.INSTANCE_TYPE, instance["url"], with_snapshots=False)

    def check(self, instance):
        """
        Integration logic
        """
        if 'url' not in instance:
            raise ConfigurationError('Missing URL in configuration.')
        if 'token' not in instance:
            raise ConfigurationError('Missing API Token in configuration.')

        self.url = instance.get('url')
        self.token = instance.get('token')
        self.tags = instance.get('tags', [])
        self.domain = instance.get('domain', '')
        self.environment = instance.get('environment', 'production')
        self.verify = instance.get('verify', True)
        self.cert = instance.get('cert', '')
        self.keyfile = instance.get('keyfile', '')

        try:
            self.start_snapshot()
            self.process_topology()
            self.stop_snapshot()
            msg = "Dynatrace topology processed successfully"
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=self.tags, message=msg)
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags, message=str(e))

    def process_topology(self):
        """
        Collects components and relations for each component type from dynatrace smartscape topology API
        """
        start_time = datetime.now()
        self.log.info("Starting the collection of topology")
        applications = self.collect_applications()
        services = self.collect_services()
        processes_groups = self.collect_process_groups()
        processes = self.collect_processes()
        hosts = self.collect_hosts()
        topology = {"application": applications, "service": services, "process-group": processes_groups,
                    "process": processes, "host": hosts}
        # collect topology for each component type
        for comp_type, response in topology.items():
            self.collect_topology(response, comp_type)
        end_time = datetime.now()
        time_taken = end_time - start_time
        self.log.info("Time taken to collect the topology is: {} seconds".format(time_taken.total_seconds()))

    def collect_relations(self, component, externalId):
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

    def filter_item_topology_data(self, data):
        """
        Delete the un-necessary relationships from the data
        """
        if "fromRelationships" in data:
            del data["fromRelationships"]
        if "toRelationships" in data:
            del data["toRelationships"]
        if "tags" in data:
            del data["tags"]

    def collect_processes(self):
        """
        Collects the response from the Dynatrace Process API endpoint
        """
        endpoint = self.get_dynatrace_endpoint("api/v1/entity/infrastructure/processes")
        processes = self.get_dynatrace_json_response(endpoint)
        return processes

    def collect_hosts(self):
        """
        Collects the response from the Dynatrace Host API endpoint
        """
        endpoint = self.get_dynatrace_endpoint("api/v1/entity/infrastructure/hosts")
        hosts = self.get_dynatrace_json_response(endpoint)
        return hosts

    def collect_applications(self):
        """
        Collects the response from the Dynatrace Application API endpoint
        """
        endpoint = self.get_dynatrace_endpoint("api/v1/entity/applications")
        applications = self.get_dynatrace_json_response(endpoint)
        return applications

    def collect_process_groups(self):
        """
        Collects the response from the Dynatrace Process-Group API endpoint
        """
        endpoint = self.get_dynatrace_endpoint("api/v1/entity/infrastructure/process-groups")
        process_groups = self.get_dynatrace_json_response(endpoint)
        return process_groups

    def collect_services(self):
        """
        Collects the response from the Dynatrace Service API endpoint
        """
        endpoint = self.get_dynatrace_endpoint("api/v1/entity/services")
        services = self.get_dynatrace_json_response(endpoint)
        return services

    def get_dynatrace_endpoint(self, path):
        """
        Creates the API endpoint from the path
        :param path: the path of the dynatrace endpoint
        :return: the full url of the endpoint
        """
        if self.url.endswith("/"):
            endpoint = self.url + path
        else:
            endpoint = self.url + "/" + path
        return endpoint

    def clean_unsupported_metadata(self, component):
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

    def get_host_identifiers(self, component):
        host_identifiers = []
        if component.get("esxiHostName"):
            host_identifiers.append("urn:host:/{}".format(component.get("esxiHostName")))
        if component.get("oneAgentCustomHostName"):
            host_identifiers.append("urn:host:/{}".format(component.get("oneAgentCustomHostName")))
        if component.get("azureHostNames"):
            host_identifiers.append("urn:host:/{}".format(component.get("azureHostNames")))
        if component.get("publicHostName"):
            host_identifiers.append("urn:host:/{}".format(component.get("publicHostName")))
        if component.get("localHostName"):
            host_identifiers.append("urn:host:/{}".format(component.get("localHostName")))
        host_identifiers.append("urn:host:/{}".format(component.get("displayName")))
        return host_identifiers

    def collect_topology(self, response, component_type):
        """
        Process each component type and map those with specific data
        :param response: Response of each component type endpoint
        :param component_type: Component type
        :return: create the component on stackstate API
        """
        if "error" in response:
            raise DynatraceError(response["error"].get("message"), response["error"].get("code"), component_type)
        for item in response:
            item = self.clean_unsupported_metadata(item)
            data = dict()
            external_id = item["entityId"]
            identifiers = ["urn:dynatrace:/{}".format(external_id)]
            if component_type == "host":
                host_identifiers = self.get_host_identifiers(item)
                identifiers.extend(host_identifiers)
            # derive useful labels and get labels from dynatrace tags
            labels = self.get_labels(item)
            data.update(item)
            self.filter_item_topology_data(data)
            data.update({
                "identifiers": identifiers,
                "tags": self.tags,
                "domain": self.domain,
                "environment": self.environment,
                "instance": self.url,
                "labels": labels
            })
            self.component(external_id, component_type, data)
            self.collect_relations(item, external_id)

    def get_labels_from_dynatrace_tags(self, item):
        """
        Process each tag as a label in component
        :param item: the component item to read from
        :return: list of added tags as labels
        """
        tags = []
        for tag in item.get("tags", []):
            tag_label = ''
            if tag.get('context') and tag.get('context') != 'CONTEXTLESS':
                tag_label += '[{0}]'.format(tag['context'])
            if tag.get('key'):
                tag_label += "{0}".format(tag['key'])
            if tag.get('value'):
                tag_label += ":{0}".format(tag['value'])
            tags.append(tag_label)
        return tags

    def get_labels(self, item):
        """
        Extract labels and tags for each component
        :param item: the component item
        :return: the list of added labels for a component
        """
        labels = []
        # append management zones in labels for each existing component
        for zone in item.get("managementZones", []):
            if zone.get("name"):
                labels.append("managementZones:{}".format(zone.get("name")))
        if item.get("entityId"):
            labels.append(item["entityId"])
        if "monitoringState" in item:
            actual_state = item["monitoringState"].get("actualMonitoringState")
            expected_state = item["monitoringState"].get("expectedMonitoringState")
            if actual_state:
                labels.append("actualMonitoringState:{}".format(actual_state))
            if expected_state:
                labels.append("expectedMonitoringState:{}".format(expected_state))
        for technologies in item.get("softwareTechnologies", []):
            tech_label = ''
            if technologies.get('type'):
                tech_label += technologies['type']
            if technologies.get('edition'):
                tech_label += ":{}".format(technologies['edition'])
            if technologies.get('version'):
                tech_label += ":{}".format(technologies['version'])
            labels.append(tech_label)
        labels_from_tags = self.get_labels_from_dynatrace_tags(item)
        labels.extend(labels_from_tags)
        # prefix the labels with `dynatrace-` for all labels
        labels = ["dynatrace-{}".format(label) for label in labels]
        return labels

    def get_dynatrace_json_response(self, endpoint, timeout=10):
        """
        Make a request to Dynatrace endpoint through session
        :param endpoint: Dynatrace API Endpoint to call
        :param timeout: timeout for a response
        :return: Response of each endpoint
        """
        headers = {"Authorization": "Api-Token {}".format(self.token)}
        resp = None
        msg = None
        self.log.info("URL is {}".format(endpoint))
        try:
            session = Session()
            session.headers.update(headers)
            session.verify = self.verify
            if self.cert:
                session.cert = (self.cert, self.keyfile)
            resp = session.get(endpoint)
            if resp.status_code != 200:
                raise Exception("Got %s when hitting %s" % (resp.status_code, endpoint))
        except requests.exceptions.Timeout:
            msg = "{} seconds timeout when hitting {}".format(timeout, endpoint)
            raise Exception("Exception occured for endpoint {0} with message: {1}".format(endpoint, msg))
        return yaml.safe_load(resp.text)
