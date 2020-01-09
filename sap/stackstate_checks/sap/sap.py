# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time
from contextlib import contextmanager

from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Transport

from stackstate_checks.base import ConfigurationError, AgentCheck, TopologyInstance


class SapCheck(AgentCheck):
    INSTANCE_TYPE = "sap"
    SERVICE_CHECK_NAME = "sap.can_connect"

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.host = None
        self.url = None
        self.user = None
        self.password = None
        self.tags = None

    def get_instance_key(self, instance):
        if "host" not in instance:
            raise ConfigurationError("Missing 'host' in instance configuration.")

        return TopologyInstance(self.INSTANCE_TYPE, instance["host"])

    def check(self, instance):
        host, url, user, password, tags = self._get_config(instance)

        if not (url and user and password):
            raise Exception("SAP url, user and password are needed.")

        # 1128 is the port of the HostControl
        host_control_url = "{0}:1128/SAPHostControl".format(url)
        with self._connect(host_control_url, user, password) as client:
            try:
                # TODO start / stop
                self._collect_topology(client)
            except Exception as e:
                self.log.exception("error!")
                self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=e, tags=self.tags)
                raise e

    def _get_config(self, instance):
        self.host = instance.get("host", "")
        self.url = instance.get("url", "")
        self.user = instance.get("user", "")
        self.password = str(instance.get("pass", ""))
        self.tags = instance.get("tags", [])

        return self.host, self.url, self.user, self.password, self.tags

    @contextmanager
    def _connect(self, url, user, password):
        try:
            session = Session()
            session.auth = HTTPBasicAuth(user, password)
            wsdl_url = "{0}/?wsdl".format(url)
            client = Client(wsdl_url, transport=Transport(session=session))
            yield client
        except Exception:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=self.tags)
            raise

    def _collect_topology(self, client):
        host_instance_ids = self._collect_hosts(client)
        self._collect_processes(host_instance_ids)
        self._collect_databases(client)

    def _collect_hosts(self, client):
        # define SAP host component
        self.component(self.host, "sap_host", {})

        instance_selector_type = client.get_type("ns0:InstanceSelector")
        instance_selector = instance_selector_type(aInstanceStatus="", aHostname=self.host)

        host_instances = client.service.ListInstances(instance_selector)
        print("host instances: {0}".format(host_instances))

        for instance in host_instances:
            sid = instance.mSid
            hostname = instance.mHostname
            host_instance_id = instance.mSystemNumber
            sap_version = instance.mSapVersionInfo

            # define SAP host instance component
            external_id = "%s:%s" % (hostname, host_instance_id)
            component_data = {
                "sid": sid,
                "host": hostname,
                "name": sid,
                "system_number": host_instance_id,
                "version": sap_version,
                "labels": []
            }
            self.component(external_id, "sap_instance", component_data)

            # define relation  host instance  -->  host
            #                              hosted-on
            source_id = external_id
            target_id = self.host
            relation_data = {}
            self.relation(source_id, target_id, "hosted-on", relation_data)

            yield host_instance_id

    # Documentation regarding SAPControl Web Service
    # TODO although describe API of SOAPHostAgent
    # https://www.sap.com/documents/2016/09/0a40e60d-8b7c-0010-82c7-eda71af511fa.html?infl=71bb5841-1684-47b2-af2d-11c623d3660e
    def _collect_processes(self, host_instance_ids):
        for host_instance_id in host_instance_ids:
            # 5xx13 is the port of the HostAgent where xx is the instance_id
            host_instance_agent_url = "{0}:5{1}13/SAPHostAgent".format(self.url, host_instance_id)
            print("instance agent url: {0}".format(host_instance_agent_url))
            with self._connect(host_instance_agent_url, self.user, self.password) as client:
                processes = client.service.GetProcessList()
                print("host {0} processes: {1}".format(host_instance_id, processes))

                for process in processes:
                    name = process.name
                    description = process.description
                    dispstatus = process.dispstatus
                    textstatus = process.textstatus
                    starttime = process.starttime
                    elapsedtime = process.elapsedtime
                    pid = process.pid

                    # define SAP process component
                    external_id = "%s:%s:%s" % (self.host, host_instance_id, pid)
                    component_data = {
                        "name": name,
                        "description": description,
                        "starttime": starttime,
                        "elapsedtime": elapsedtime,
                        "pid": pid,
                        "labels": []
                    }
                    self.component(external_id, "sap_process", component_data)

                    # define relation  process  -->  host
                    #                         runs-on
                    relation_data = {}
                    source_id = external_id
                    target_id = "%s:%s" % (self.host, host_instance_id)
                    self.relation(source_id, target_id, "runs-on", relation_data)

                    # define process status event
                    self.event({
                        "timestamp": int(time.time()),
                        "source_type_name": "SAP:process state",
                        "msg_title": "Process pid {0} status update.".format(pid),
                        "msg_text": textstatus,
                        "host": self.host,
                        "tags": [
                            "status:{0}".format(dispstatus),
                            "pid:{0}".format(pid),
                            "instance:{0}".format(host_instance_id)
                        ]
                    })

    def _collect_databases(self, client):
        properties_type = client.get_type("ns0:ArrayOfProperty")
        properties = properties_type()
        databases = client.service.ListDatabases(properties)
        print("databases: {0}".format(databases))

        for database in databases:
            # define database component
            database_item = {i.mKey: i.mValue for i in database.mDatabase.item}
            database_name = database_item.get("Database/Name")
            external_id = "%s:%s" % (self.host, database_name)
            component_data = {
                "name": database_name,
                "database_type": database_item.get("Database/Type"),
                "database_vendor": database_item.get("Database/Vendor"),
                "database_host": database_item.get("Database/Host"),
                "instance_name": database_item.get("Database/InstanceName"),
                "version": database_item.get("Database/Release"),
                "labels": []
            }
            self.component(external_id, "sap_database", component_data)

            # define relation  database  -->  host
            #                         hosted-on
            source_id = external_id
            target_id = self.host
            relation_data = {}
            self.relation(source_id, target_id, "hosted-on", relation_data)

            # define database status event
            database_status = database.mStatus
            self.event({
                "timestamp": int(time.time()),
                "source_type_name": "SAP:database state",
                "msg_title": "Database {0} status update.".format(database_name),
                "host": self.host,
                "tags": [
                    "status:{0}".format(database_status),
                    "database_name:{0}".format(database_name)
                ]
            })

            for database_component in database.mComponents.item:
                # define database component
                # TODO this is confusing, use database instances ?
                database_component_item = {i.mKey: i.mValue for i in database_component.mProperties.item}
                database_component_name = database_component_item.get("Database/ComponentName")
                database_component_external_id = "%s:%s" % (external_id, database_component_name)
                database_component_data = {
                    "name": database_component_name,
                    "description": database_component_item.get("Database/ComponentDescription"),
                    "labels": []
                }
                self.component(database_component_external_id, "sap_database_component", database_component_data)

                # define relation between database component  -->  database
                #                                           runs-on
                database_component_relation_source_id = database_component_external_id
                database_component_relation_target_id = external_id
                database_component_relation_data = {}
                self.relation(database_component_relation_source_id, database_component_relation_target_id, "runs-on",
                              database_component_relation_data)

                # define database component status event
                self.event({
                    "timestamp": int(time.time()),
                    "source_type_name": "SAP:database component state",
                    "msg_title": "Database component {0} status update.".format(database_component_name),
                    "host": self.host,
                    "tags": [
                        "status:{0}".format(database_component_item.get("Database/ComponentStatusDescription")),
                        "database_component_name:%s".format(database_component_name)
                    ]
                })
