# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance

import requests
from requests import Session
import yaml
from datetime import datetime


class DynatraceCheck(AgentCheck):

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
            raise ConfigurationError('Missing API url in configuration.')

        return TopologyInstance(self.INSTANCE_TYPE, instance["url"])

    def check(self, instance):
        """
        Integration logic
        """
        if 'url' not in instance:
            raise ConfigurationError('Missing API user in configuration.')
        if 'token' not in instance:
            raise ConfigurationError('Missing API Token in configuration.')

        self.url = instance.get('url')
        self.token = instance.get('token')
        self.tags = instance.get('tags', [])
        self.environment = instance.get('environment', 'production')
        self.verify = instance.get('verify', True)
        self.cert = instance.get('cert', '')
        self.keyfile = instance.get('keyfile', '')

        try:
            self.start_snapshot()
            self.process_topology()
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags, message=str(e))
        finally:
            self.stop_snapshot()

    def process_topology(self):
        """
        Collects each component type from dynatrace smartscape topology API
        """
        start_time = datetime.now()
        self.log.info("Starting the collection of topology")
        self.collect_services()
        self.collect_processes()
        self.collect_proccess_groups()
        self.collect_hosts()
        self.collect_applications()
        end_time = datetime.now()
        time_taken = end_time - start_time
        self.log.info("Time taken to collect the topology is: {}".format(time_taken.total_seconds()))

    def collect_relations(self, component, externalId):
        """
        Collects relationships from different component-types
        :param component: the component for which relationships need to be extracted and processed
        :param externalId: the component externalId for and from relationship will be created
        :return: None
        """
        outgoing_relations = component.get("fromRelationships", {})
        incoming_relations = component.get("toRelationships", {})
        for relation_type in outgoing_relations.keys():
            for target_id in outgoing_relations[relation_type]:
                self.relation(externalId, target_id, relation_type, {})
        for relation_type in incoming_relations.keys():
            for source_id in incoming_relations[relation_type]:
                self.relation(source_id, externalId, relation_type, {})

    def filter_data(self, data):
        """
        Delete the un-necessary relationships from the data
        """
        if "fromRelationships" in data:
            del data["fromRelationships"]
        if "toRelationships" in data:
            del data["toRelationships"]
        return data

    def collect_processes(self):
        """
        Collects all processes from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/infrastructure/processes"
        processes = self.get_json_response(endpoint)
        self.process_component(processes, "process")

    def collect_hosts(self):
        """
        Collects all hosts from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/infrastructure/hosts"
        hosts = self.get_json_response(endpoint)
        self.process_component(hosts, "host")

    def collect_applications(self):
        """
        Collects all applications from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/applications"
        applications = self.get_json_response(endpoint)
        self.process_component(applications, "application")

    def collect_proccess_groups(self):
        """
        Collects all process-groups from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/infrastructure/process-groups"
        process_groups = self.get_json_response(endpoint)
        self.process_component(process_groups, "process-group")

    def collect_services(self):
        """
        Collects all services from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/services"
        services = self.get_json_response(endpoint)
        self.process_component(services, "service")

    def process_component(self, response, component_type):
        """
        Process each component type and map those with specific data
        :param response: Response of each component type endpoint
        :param component_type: Component type
        :return: create the component on stackstate API
        """
        urn = ''
        if type(response) is not dict and "error" not in response:
            for item in response:
                # special case for host type as we get some float values
                if component_type == "host":
                    for key in item.keys():
                        if type(item[key]) is float:
                            item[key] = int(item[key])
                identifiers = []
                labels = []
                externalId = item.get("entityId")
                if component_type == "service":
                    urn = "urn:service:/{}".format(externalId)
                elif component_type == "process-group":
                    urn = "urn:process-group:/{}".format(externalId)
                elif component_type == "application":
                    urn = "urn:application:/{}".format(externalId)
                elif component_type == "process":
                    urn = "urn:process:/{}".format(externalId)
                elif component_type == "host":
                    displayName = item.get("displayName")
                    urn = "urn:host:/{}".format(displayName)
                identifiers.append(urn)
                # tags = [tag.get("key") for tag in item.get("tags", [])] + self.tags
                tags = self.add_tags(item)
                if "tags" in item:
                    del item["tags"]
                labels = self.add_labels(item, labels)
                data = {
                    "identifiers": identifiers,
                    "tags": tags,
                    "domain": self.domain,
                    "environment": self.environment,
                    "instance": self.url,
                    "labels": labels
                }
                data.update(item)
                data = self.filter_data(data)
                self.component(externalId, component_type, data)
                self.collect_relations(item, externalId)
        else:
            self.log.info("Problem getting the {0} or No {1} found.".format(type, type))

    def add_tags(self, item):
        tags = []
        for tag in item.get("tags", []):
            tag_label = ''
            if bool(tag['context']) and tag.get('context') != 'CONTEXTLESS':
                tag_label += '[{0}]'.format(tag['context'])
            if bool(tag.get('key')):
                tag_label += "{0}".format(tag['key'])
            if bool(tag.get('value')):
                tag_label += ":{0}".format(tag['value'])
            tags.append(tag_label)
        return tags

    def add_labels(self, item, labels):
        """
        Add labels for each component
        :param item: the component item
        :param labels: empty labels list where to add specific labels
        :return: the list of added labels for a component
        """
        # append management zones in labels for each existing component
        if "managementZones" in item:
            for zone in item["managementZones"]:
                labels.append("managementZones:{}".format(zone.get("name)")))
        if "entityId" in item:
            labels.append(item["entityId"])
        if "monitoringState" in item:
            actual_state = item["monitoringState"].get("actualMonitoringState")
            expected_state = item["monitoringState"].get("expectedMonitoringState")
            labels.append("actualMonitoringState:{}".format(actual_state))
            labels.append("expectedMonitoringState:{}".format(expected_state))
        if "softwareTechnologies" in item:
            for technologies in item["softwareTechnologies"]:
                tech_label = ''
                if bool(technologies['type']):
                    tech_label += technologies['type']
                if bool(technologies['edition']):
                    tech_label += ":{}".format(technologies['edition'])
                if bool(technologies['version']):
                    tech_label += ":{}".format(technologies['version'])
                labels.append(tech_label)
        return labels

    def get_json_response(self, endpoint, timeout=10):
        headers = {"Authorization": "Api-Token {}".format(self.token)}
        status = None
        resp = None
        msg = None
        self.log.info("URL is {}".format(endpoint))
        try:
            session = Session()
            session.headers.update(headers)
            if self.cert:
                session.verify = self.verify
                session.cert = (self.cert, self.keyfile)
            resp = session.get(endpoint)
        except requests.exceptions.Timeout:
            msg = "{} seconds timeout when hitting {}".format(timeout, endpoint)
            status = AgentCheck.CRITICAL
        except Exception as e:
            msg = str(e)
            status = AgentCheck.CRITICAL
        finally:
            if status is AgentCheck.CRITICAL:
                self.service_check(self.SERVICE_CHECK_NAME, status, tags=[],
                                   message=msg)
                raise Exception("Exception occured for endpoint {0} with message: {1}".format(endpoint, msg))
        return yaml.safe_load(resp.text)
