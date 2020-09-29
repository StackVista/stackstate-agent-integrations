# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance

import requests
import yaml
from datetime import datetime


class DynatraceCheck(AgentCheck):

    INSTANCE_TYPE = "dynatrace"
    SERVICE_CHECK_NAME = "dynatrace"

    def __init__(self, name, init_config, instances=None):
        AgentCheck.__init__(self, name, init_config, instances)
        self.url = None
        self.token = None
        self.tags = None
        self.environment = None
        self.domain = None

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

        try:
            self.start_snapshot()
            self.process_topology()
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags, message=str(e))
        finally:
            self.stop_snapshot()

    def process_topology(self):
        # Collect each component type from dynatrace smartscape topology API
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
        outgoing_relations = component.get("fromRelationships")
        incoming_relations = component.get("toRelationships")
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
        del data["fromRelationships"]
        del data["toRelationships"]
        return data

    def collect_processes(self):
        """
        Collects all processes from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/infrastructure/processes"
        processes = self.get_json_response(endpoint)
        if type(processes) is not dict and "error" not in processes:
            for process in processes:
                identifiers = []
                externalId = process.get("entityId")
                component_type = "process"
                process_urn = "urn:process:/{}".format(externalId)
                identifiers.append(process_urn)
                data = {
                    "identifiers": identifiers,
                    "tags": self.tags,
                    "domain": self.domain,
                    "environment": self.environment,
                    "instance": self.url
                }
                data.update(process)
                data = self.filter_data(data)
                self.component(externalId, component_type, data)
                self.collect_relations(process, externalId)
        else:
            self.log.info("Problem getting the processes or No processes found.")

    def collect_hosts(self):
        """
        Collects all hosts from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/infrastructure/hosts"
        hosts = self.get_json_response(endpoint)
        if type(hosts) is not dict and "error" not in hosts:
            for host in hosts:
                for key in host.keys():
                    if type(host[key]) is float:
                        host[key] = str(host[key])
                identifiers = []
                externalId = host.get("entityId")
                displayName = host.get("displayName")
                host_urn = "urn:host:/{}".format(displayName)
                component_type = "host"
                identifiers.append(host_urn)
                data = {
                    "identifiers": identifiers,
                    "tags": self.tags,
                    "domain": self.domain,
                    "environment": self.environment,
                    "instance": self.url
                }
                data.update(host)
                data = self.filter_data(data)
                self.component(externalId, component_type, data)
                self.collect_relations(host, externalId)
        else:
            self.log.info("Problem getting the hosts or No hosts found.")

    def collect_applications(self):
        """
        Collects all applications from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/applications"
        applications = self.get_json_response(endpoint)
        if type(applications) is not dict and "error" not in applications:
            for application in applications:
                identifiers = []
                externalId = application.get("entityId")
                component_type = "application"
                application_urn = "urn:application:/{}".format(externalId)
                identifiers.append(application_urn)
                data = {
                    "identifiers": identifiers,
                    "tags": self.tags,
                    "domain": self.domain,
                    "environment": self.environment,
                    "instance": self.url
                }
                data.update(application)
                data = self.filter_data(data)
                self.component(externalId, component_type, data)
                self.collect_relations(application, externalId)
        else:
            self.log.info("Problem getting the applications or No applications found.")

    def collect_proccess_groups(self):
        """
        Collects all process-groups from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/infrastructure/process-groups"
        process_groups = self.get_json_response(endpoint)
        if type(process_groups) is not dict and "error" not in process_groups:
            for process_group in process_groups:
                identifiers = []
                externalId = process_group.get("entityId")
                component_type = "process-group"
                process_group_urn = "urn:process-group:/{}".format(externalId)
                identifiers.append(process_group_urn)
                data = {
                    "identifiers": identifiers,
                    "tags": self.tags,
                    "domain": self.domain,
                    "environment": self.environment,
                    "instance": self.url
                }
                data.update(process_group)
                data = self.filter_data(data)
                self.component(externalId, component_type, data)
                self.collect_relations(process_group, externalId)
        else:
            self.log.info("Problem getting the process-groups or No process-groups found.")

    def collect_services(self):
        """
        Collects all services from Dynatrace API and their relationships with other component types if exists
        """
        endpoint = self.url + "/api/v1/entity/services"
        services = self.get_json_response(endpoint)
        if type(services) is not dict and "error" not in services:
            for service in services:
                identifiers = []
                externalId = service.get("entityId")
                service_urn = "urn:service:/{}".format(externalId)
                component_type = "service"
                identifiers.append(service_urn)
                data = {
                    "identifiers": identifiers,
                    "tags": self.tags,
                    "domain": self.domain,
                    "environment": self.environment,
                    "instance": self.url
                }
                data.update(service)
                data = self.filter_data(data)
                self.component(externalId, component_type, data)
                self.collect_relations(service, externalId)
        else:
            self.log.info("Problem getting the services or No services found.")

    def get_json_response(self, endpoint, timeout=10):
        headers = {"Authorization": "Api-Token {}".format(self.token)}
        status = None
        resp = None
        msg = None
        self.log.info("URL is {}".format(endpoint))
        try:
            resp = requests.get(endpoint, headers=headers)
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
