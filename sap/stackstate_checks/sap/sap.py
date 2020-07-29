# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import logging
import time

from stackstate_checks.base import ConfigurationError, AgentCheck, TopologyInstance
from .proxy import SapProxy


class SapCheck(AgentCheck):
    INSTANCE_TYPE = "sap"
    SERVICE_CHECK_NAME = "sap.can_connect"

    def __init__(self, name, init_config, instances=None):
        AgentCheck.__init__(self, name, init_config, instances)
        self.host = None
        self.url = None
        self.user = None
        self.password = None
        self.tags = None

        # `zeep` logs lots of stuff related to wsdl parsing on DEBUG level so we avoid that
        zeep_logger = logging.getLogger("zeep")
        zeep_logger.setLevel(logging.WARN)
        zeep_logger.propagate = True

    def get_instance_key(self, instance):
        if "host" not in instance:
            raise ConfigurationError("Missing 'host' in instance configuration.")

        return TopologyInstance(self.INSTANCE_TYPE, instance["host"])

    def check(self, instance):
        host, url, user, password, tags = self._get_config(instance)

        if not (url and user and password):
            raise ConfigurationError("Missing 'url', 'user' or 'password' in instance configuration.")

        try:
            self.start_snapshot()

            self._collect_topology()

            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, message="OK", tags=self.tags)
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e), tags=self.tags)
        finally:
            self.stop_snapshot()

    def _get_config(self, instance):
        self.host = instance.get("host", "")
        self.url = instance.get("url", "")
        self.user = instance.get("user", "")
        self.password = str(instance.get("pass", ""))
        self.verify = instance.get("verify", True)
        self.cert = instance.get("cert", "")
        self.keyfile = instance.get("keyfile", "")
        self.tags = instance.get("tags", [])

        return self.host, self.url, self.user, self.password, self.tags

    def _collect_topology(self):
        host_instances = self._collect_hosts()
        self._collect_instance_processes_and_metrics(host_instances)
        self._collect_databases()

    def _get_proxy(self, instance_id=None):
        if not instance_id:
            # 1128 is the port of the HostControl for HTTP protocol
            host_port = "1128"
            if self.cert:
                # for HTTPS protocol, 1129 is the port of the HostControl
                host_port = "1129"
            host_control_url = "{0}:{1}/SAPHostControl".format(self.url, host_port)
            return SapProxy(host_control_url, self.user, self.password, self.verify, self.cert, self.keyfile)
        else:
            # 5xx13 is the port of the HostAgent where xx is the instance_id
            if self.cert:
                host_instance_agent_url = "{0}:5{1}14/SAPHostAgent".format(self.url, instance_id)
            else:
                host_instance_agent_url = "{0}:5{1}13/SAPHostAgent".format(self.url, instance_id)
            return SapProxy(host_instance_agent_url, self.user, self.password, self.verify, self.cert, self.keyfile)

    def _collect_hosts(self):
        try:
            # define SAP host control component
            self.component(self._host_external_id(), "sap-host", {"host": self.host})

            host_control_proxy = self._get_proxy()
            host_instances = host_control_proxy.get_sap_instances()
            self.log.debug("host instances: {0}".format(host_instances))

            instances = {}
            if host_instances:
                for instance in host_instances:
                    instance_item = {i.mName: i.mValue for i in instance.mProperties.item}

                    sid = instance_item.get("SID")
                    instance_id = instance_item.get("SystemNumber")
                    instance_type = instance_item.get("InstanceType")
                    sap_version = instance_item.get("SapVersionInfo")
                    # hostname = instance_item.get("Hostname") # same as self.host

                    # define SAP host instance component
                    external_id = self._host_instance_external_id(instance_id)
                    component_data = {
                        "sid": sid,
                        "host": self.host,
                        "name": sid,
                        "system_number": instance_id,
                        "type": instance_type,
                        "version": sap_version,
                        "labels": []
                    }
                    self.component(external_id, "sap-instance", component_data)

                    # define relation  host instance    -->    host
                    #                              is hosted on
                    source_id = external_id
                    target_id = self._host_external_id()
                    relation_data = {}
                    self.relation(source_id, target_id, "is hosted on", relation_data)

                    instances.update({instance_id: instance_type})

            # publish event if we connected successfully to the SAP host control
            self.event({
                "timestamp": int(time.time()),
                "source_type_name": "SAP:host control",
                "msg_title": "Host control '{0}' status update.".format(self.host),
                "msg_text": "",
                "host": self.host,
                "tags": [
                    "status:sap-host-control-success",
                    "host:{0}".format(self.host)
                ]
            })

            return instances
        except Exception as e:
            self.log.exception(str(e))

            # publish event if we could NOT connect to the SAP host control
            self.event({
                "timestamp": int(time.time()),
                "source_type_name": "SAP:host control",
                "msg_title": "Host control '{0}' status update.".format(self.host),
                "msg_text": str(e),
                "host": self.host,
                "tags": [
                    "status:sap-host-control-error",
                    "host:{0}".format(self.host)
                ]
            })

    # Documentation regarding SAPControl Web Service, which describes API of SOAPHostAgent
    # https://www.sap.com/documents/2016/09/0a40e60d-8b7c-0010-82c7-eda71af511fa.html?infl=71bb5841-1684-47b2-af2d-11c623d3660e
    def _collect_instance_processes_and_metrics(self, host_instances):
        for instance_id, instance_type in list(host_instances.items()):
            try:
                host_instance_proxy = self._get_proxy(instance_id)

                self._collect_processes(instance_id, host_instance_proxy)

                self._collect_memory_metric(instance_id, host_instance_proxy)

                self._collect_worker_metrics(instance_id, instance_type, host_instance_proxy)

                # publish event if we connected successfully to the SAP host instance
                self.event({
                    "timestamp": int(time.time()),
                    "source_type_name": "SAP:host instance",
                    "msg_title": "Host instance '{0}' status update.".format(instance_id),
                    "msg_text": "",
                    "host": self.host,
                    "tags": [
                        "status:sap-host-instance-success",
                        "instance_id:{0}".format(instance_id)
                    ]
                })
            except Exception as e:
                self.log.exception(str(e))

                # publish event if we could NOT connect to the SAP host instance
                self.event({
                    "timestamp": int(time.time()),
                    "source_type_name": "SAP:host instance",
                    "msg_title": "Host instance '{0}' status update.".format(instance_id),
                    "msg_text": str(e),
                    "host": self.host,
                    "tags": [
                        "status:sap-host-instance-error",
                        "instance_id:{0}".format(instance_id)
                    ]
                })

    def _collect_processes(self, instance_id, host_instance_proxy):
        processes = host_instance_proxy.get_sap_instance_processes()
        self.log.debug("host instance '{0}' processes: {1}".format(instance_id, processes))
        for process in processes:
            name = process.name
            description = process.description
            dispstatus = process.dispstatus
            textstatus = process.textstatus
            starttime = process.starttime
            elapsedtime = process.elapsedtime
            pid = int(process.pid)

            # define SAP process component
            # TODO use process name in externalId for process
            external_id = self._process_external_id(instance_id, pid)
            component_data = {
                "name": name,
                "description": description,
                "starttime": starttime,
                "elapsedtime": elapsedtime,
                "pid": pid,
                "host": self.host,
                "labels": []
            }
            self.component(external_id, "sap-process", component_data)

            # define relation  process  -->  host instance
            #                         runs on
            source_id = external_id
            target_id = self._host_instance_external_id(instance_id)
            relation_data = {}
            self.relation(source_id, target_id, "runs on", relation_data)

            # define process status event
            self.event({
                "timestamp": int(time.time()),
                "source_type_name": "SAP:process state",
                "msg_title": "Process pid '{0}' status update.".format(pid),
                "msg_text": textstatus,
                "host": self.host,
                "tags": [
                    "status:{0}".format(dispstatus),
                    "pid:{0}".format(pid),
                    "instance_id:{0}".format(instance_id),
                    "starttime:{0}".format(starttime),
                ]
            })

    def _collect_worker_metrics(self, instance_id, instance_type, host_instance_proxy):
        if instance_type.startswith("ABAP"):
            interesting_workers = ["DIA", "BTC"]
            num_free_workers = host_instance_proxy.get_sap_instance_abap_free_workers(interesting_workers)
            self.log.debug("number of worker processes for instance '{0}': {1}".format(
                instance_id, num_free_workers))
            for worker_type, num_free_worker in list(num_free_workers.items()):
                self.gauge(
                    name="{0}_workers_free".format(worker_type),
                    value=num_free_worker,
                    tags=["instance_id:{0}".format(instance_id)],
                    hostname=self.host
                )

    def _collect_memory_metric(self, instance_id, host_instance_proxy):
        phys_memsize = host_instance_proxy.get_sap_instance_physical_memory()
        self.log.debug("host instance '{0}' physical memory: {1}".format(instance_id, phys_memsize))
        self.gauge(
            name="phys_memsize",
            value=phys_memsize,
            tags=["instance_id:{0}".format(instance_id)],
            hostname=self.host
        )

    def _collect_databases(self):
        host_control_proxy = self._get_proxy()
        databases = host_control_proxy.get_databases()
        self.log.debug("databases: {0}".format(databases))

        if databases:
            for database in databases:
                # define database component
                database_item = {i.mKey: i.mValue for i in database.mDatabase.item}
                database_name = database_item.get("Database/Name")
                external_id = self._db_external_id(database_name)
                component_data = {
                    "name": database_name,
                    "type": database_item.get("Database/Type"),
                    "vendor": database_item.get("Database/Vendor"),
                    "host": database_item.get("Database/Host").lower(),
                    "version": database_item.get("Database/Release"),
                    "labels": []
                }
                self.component(external_id, "sap-database", component_data)

                # define relation  database    -->    host
                #                          is hosted on
                source_id = external_id
                target_id = self._host_external_id()
                relation_data = {}
                self.relation(source_id, target_id, "is hosted on", relation_data)

                # define database status event
                database_status = database.mStatus
                self.event({
                    "timestamp": int(time.time()),
                    "source_type_name": "SAP:database state",
                    "msg_title": "Database '{0}' status update.".format(database_name),
                    "msg_text": "",
                    "host": self.host,
                    "tags": [
                        "status:{0}".format(database_status),
                        "database_name:{0}".format(database_name)
                    ]
                })

                for database_component in database.mComponents.item:
                    # define database component
                    database_component_item = {i.mKey: i.mValue for i in database_component.mProperties.item}
                    database_component_name = database_component_item.get("Database/ComponentName")
                    database_component_external_id = self._db_component_external_id(
                        database_name=database_name,
                        database_component_name=database_component_name
                    )
                    database_component_data = {
                        "name": database_component_name,
                        "database_name": database_name,
                        "description": database_component_item.get("Database/ComponentDescription"),
                        "host": self.host,
                        "labels": []
                    }
                    self.component(database_component_external_id, "sap-database-component", database_component_data)

                    # define relation between database component  -->  database
                    #                                           runs on
                    database_component_relation_source_id = database_component_external_id
                    database_component_relation_target_id = external_id
                    database_component_relation_data = {}
                    self.relation(
                        source=database_component_relation_source_id,
                        target=database_component_relation_target_id,
                        type="runs on",
                        data=database_component_relation_data
                    )

                    # define database component status event
                    self.event({
                        "timestamp": int(time.time()),
                        "source_type_name": "SAP:database component state",
                        "msg_title": "Database component '{0}' status update.".format(database_component_name),
                        "msg_text": "",
                        "host": self.host,
                        "tags": [
                            "status:{0}".format(database_component.mStatus),
                            "database_component_name:{0}".format(database_component_name)
                        ]
                    })

    def _host_external_id(self):
        return "urn:host:/{0}".format(self.host)

    def _host_instance_external_id(self, host_instance_id):
        return "urn:sap:/instance:{0}:{1}".format(self.host, host_instance_id)

    def _process_external_id(self, host_instance_id, pid):
        return "urn:process:/{0}:{1}:{2}".format(self.host, host_instance_id, pid)

    def _db_external_id(self, database_name):
        return "urn:db:/{0}:{1}".format(self.host, database_name)

    def _db_component_external_id(self, database_name, database_component_name):
        return "urn:sap:/db_component:{0}:{1}:{2}".format(self.host, database_name, database_component_name)
