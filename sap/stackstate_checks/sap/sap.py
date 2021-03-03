# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import logging
import time
from requests import Session
from requests.auth import HTTPBasicAuth
from requests.packages import urllib3
from threading import Thread
# import sys
try:
    from Queue import Empty, Queue  # Python3
except ImportError:
    from queue import Empty, Queue  # Python2
import json
from stackstate_checks.base import ConfigurationError, AgentCheck, TopologyInstance
from .proxy import SapProxy
from .events import Events
from .gauges import Gauges


class SapCheck(AgentCheck):
    queue = {}
    INSTANCE_TYPE = "sap"
    SERVICE_CHECK_NAME = "sap.can_connect"
    DEFAULT_THREAD_COUNT = 0        # Python2 multithreading not (yet) working. Set to 0 to disable multithreading.
    DEFAULT_IDLE_THREAD_TTL = 30    # Value in Seconds.

    def __init__(self, name, init_config, instances=None):
        AgentCheck.__init__(self, name, init_config, instances)
        self.host = None
        self.url = None
        self.user = None
        self.password = None
        self.tags = None
        self.domain = None
        self.stackstate_environment = None

        # `zeep` logs lots of stuff related to wsdl parsing on DEBUG level so we avoid that
        zeep_logger = logging.getLogger("zeep")
        zeep_logger.setLevel(logging.WARN)
        zeep_logger.propagate = True

    def get_instance_key(self, instance):
        if "host" not in instance:
            raise ConfigurationError("Missing 'host' in instance configuration.")

        return TopologyInstance(self.INSTANCE_TYPE, instance["host"])

    def start_threads(self, count=DEFAULT_THREAD_COUNT, timeout=DEFAULT_IDLE_THREAD_TTL):
        """
        Create and start <count> threads as background processes.\n
        Use count = 0 to disable multithreading\n
        :param count: The number of worker threads to create. Hardcoded limit of 16
        :param timeout: The number of seconds after an idle thread dies. Hardcoded limit of 3600 seconds (1 hour)
        """
        if (int(count) in range(17)) and (int(timeout) in range(3601)) and (int(count) > 0):
            # Create queue for events and metrics to send, only if none exists
            if self.host not in self.queue.keys():
                self.queue[self.host] = Queue()
            for _ in range(count):
                # Create and start worker threads
                Thread(target=self.thread_worker, args=(self.queue[self.host], timeout)).start()

    @staticmethod
    def thread_worker(backlog, timeout=DEFAULT_IDLE_THREAD_TTL):
        """
        Thread function that does the actual work of pushing data to server.\n
        Takes (first) object from backlog queue, separates function from
        parameters and calls function with parameters.\n
        Infinite loop with timeout.\n
        If backlog is empty for <timeout> seconds this function kills itself.\n
        :param backlog: Queue object with function(with parameters) objects.
        :param timeout: Number of seconds to wait for jobs in queue.
        """
        while True:  # infinite loop until backlog is empty
            try:
                func, args = backlog.get(timeout=timeout)  # Claim next item in queue, wait <timeout> seconds
            except Empty:
                # sys.stdout.write("thread_worker: No more work in queue")
                return  # stop which also kills the thread.
            # sys.stdout.write("thread_worker->{}(..,{},..)".format(func, args[1]))
            func(*args)
            backlog.task_done()  # Delete claimed item from backlog

    def check(self, instance):
        url, user, password = self._get_config(instance)

        if not (url and user and password):
            raise ConfigurationError("Missing 'url', 'user' or 'password' in instance configuration.")

        start_time = time.time()
        try:
            self.start_threads(self.thread_count, self.thread_timeout)
            self.log.info("{0}: Checks started".format(self.host))
            self.start_snapshot()
            snapshot1_time = time.time()
            lap_time = snapshot1_time-start_time
            self.log.info("{0}: start_snapshot run time is {1}Seconds".format(self.host, lap_time))
            self._collect_topology()
            topology_time = time.time()
            lap_time = topology_time-snapshot1_time
            self.log.info("{0}: _collect_topology run time is {1}Seconds".format(self.host, lap_time))

            self._collect_metrics()
            metrics_time = time.time()
            lap_time = metrics_time-topology_time
            self.log.info("{0}: _collect_metrics run time is {1}Seconds".format(self.host, lap_time))

            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, message="OK", tags=self.tags)
            service_time = time.time()
            lap_time = service_time-metrics_time
            self.log.info("{0}: service_check run time is {1}Seconds".format(self.host, lap_time))
        except Exception as e:
            # sys.stdout.write("check: Exception\n{}\n".format(e))
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e), tags=self.tags)
        finally:
            if self.host in self.queue.keys():
                self.queue[self.host].join()  # Waits/Blocks until self.queue is empty...
            self.stop_snapshot()
            snapshot2_time = time.time()
            try:
                lap_time = snapshot2_time-service_time
                self.log.info("{0}: Drain queue & stop_snapshot run time is {1}Seconds".format(self.host, lap_time))
            except NameError:
                self.log.info("{0}: Exception occured, measuments unavailable".format(self.host))
            stop_time = time.time()
            run_time = stop_time-start_time
            self.log.info("{0}: Check total run time is {1}Seconds".format(self.host, run_time))

    def _get_config(self, instance):
        self.host = instance.get("host", "")
        self.url = instance.get("url", "")
        self.user = instance.get("user", "")
        self.password = str(instance.get("pass", ""))
        self.verify = instance.get("verify", True)
        self.cert = instance.get("cert", "")
        self.keyfile = instance.get("keyfile", "")
        self.domain = instance.get("domain", None)
        self.stackstate_environment = instance.get("environment", None)
        self.thread_count = int(instance.get('thread_count', self.DEFAULT_THREAD_COUNT))
        self.thread_timeout = int(instance.get('idle_thread_ttl', self.DEFAULT_IDLE_THREAD_TTL))
        self.tags = instance.get("tags", [])
        return self.url, self.user, self.password

    def _collect_topology(self):
        host_instances = self._collect_hosts()
        proxy = self._get_proxy()
        if host_instances:
            self._collect_instance_processes_and_metrics(host_instances, proxy)
        self._collect_databases(proxy)
        self._collect_sapcloudconnector()
        self._collect_saprouter(proxy)

    def _collect_metrics(self):
        """
        We get all alerts and selected metrics from all the instances and databases.\n
        We send back only what is required.
        """
        proxy = self._get_proxy()

        instances = proxy.get_sap_instances()
        if instances:
            for instance in instances:
                data = {i.mName: i.mValue for i in instance.mProperties.item}
                instance_id = data.get("SystemNumber")
                self._get_instance_params(instance_id, proxy)
        self._get_computersystem(proxy)
        # SAP_ITSAMDatabaseMetric
        databases = proxy.get_databases()
        if databases:
            for database in databases:
                # Cannot query a database that's not up
                if not (database.mStatus in ["SAPHostControl-DB-WARNING", "SAPHostControl-DB-RUNNING"]):
                    continue
                data = {i.mKey: i.mValue for i in database.mDatabase.item}
                name = data.get("Database/Name")
                dbtype = data.get("Database/Type")
                self._get_database_gauges(name, proxy, dbtype)
                self._get_database_events(name, proxy, dbtype)

    def _get_database_events(self, name, proxy, dbtype):
        # SAP_ITSAMDatabaseMetric events
        events = ";".join(Events.dbmetric_events.keys())
        query = "SAP_ITSAMDatabaseMetric?Name={0}&Type={1}&ID={2}".format(name, dbtype, events)
        metrics = proxy.get_cim_object("EnumerateInstances", query)
        for metriclist in metrics:
            for metric in metriclist.mMembers.item:
                data = {i.mName: i.mValue for i in metric.mProperties.item}
                metricid = data.get("MetricID")
                if metricid in Events.dbmetric_events.keys():
                    lookup = Events.dbmetric_events.get(metricid)
                    description = lookup.get("description", metricid)
                    status = data.get(lookup.get("field"))
                    taglist = self.generate_tags(data=data, status=status, database=name)
                    if self.host in self.queue.keys():
                        self.queue[self.host].put((self.send_event, [description, taglist]))
                    else:
                        self.send_event(description, taglist)

    def _get_database_gauges(self, name, proxy, dbtype):
        # SAP_ITSAMDatabaseMetric gauges
        gauges = ";".join(Gauges.dbmetric_gauges.keys())
        query = "SAP_ITSAMDatabaseMetric?Name={0}&Type={1}&ID={2}".format(name, dbtype, gauges)
        metrics = proxy.get_cim_object("EnumerateInstances", query)
        # sys.stdout.write("_get_database_gauges performed query={}\n".format(query))
        for metriclist in metrics:
            for metric in metriclist.mMembers.item:
                metricdata = {i.mName: i.mValue for i in metric.mProperties.item}
                metricid = metricdata.get("MetricID")
                if metricid in Gauges.dbmetric_gauges.keys():
                    lookup = Gauges.dbmetric_gauges.get(metricid)
                    description = lookup.get("description", metricid)
                    value = metricdata.get(lookup.get("field"))
                    taglist = ["host:{}".format(self.host), "database:{}".format(name)]
                    for tag in self.tags:
                        taglist.append(tag)
                    # sys.stdout.write("_get_database_gauges\ndescription={}\nvalue={}\ntaglist={}".format(description,
                    #                                                                                      value,
                    #                                                                                      taglist))
                    if self.host in self.queue.keys():
                        self.queue[self.host].put((self.send_gauge, [description, value, taglist]))
                    else:
                        self.send_gauge(description, value, taglist)

    def _get_computersystem(self, proxy):
        # GetComputerSystem gauges
        metrics = proxy.get_computerSystem()
        if metrics:
            metric_item = {i.mName: i.mValue for i in metrics.mMembers.item[0].mProperties.item}
            for item in metric_item:
                if item in Gauges.system_gauges.keys():
                    description = Gauges.system_gauges.get(item).get("description", item)
                    value = metric_item.get(item)
                    taglist = ["host:{}".format(self.host)]
                    for tag in self.tags:
                        taglist.append(tag)
                    # sys.stdout.write("_get_computersystem:\nvalue={}\ndescription={}\ntaglist={}".format(value,
                    #                                                                                      description,
                    #                                                                                      taglist))
                    if self.host in self.queue.keys():
                        self.queue[self.host].put((self.send_gauge, [description, value, taglist]))
                    else:
                        self.send_gauge(description, value, taglist)

    def _get_instance_params(self, instance_id, proxy):
        # SAP_ITSAMInstance/Parameter
        params = proxy.get_sap_instance_params(instance_id)
        for param in params.keys():
            if param in Gauges.instance_gauges.keys():
                description = Gauges.instance_gauges.get(param).get("description", param)
                value = params.get(param)
                taglist = ["instance_id:{0}".format(instance_id), "host:{0}".format(self.host)]
                for tag in self.tags:
                    taglist.append(tag)
                # sys.stdout.write("_get_instance_params\n\tvalue={}\n\ttaglist={}\n".format(value, taglist))
                if self.host in self.queue.keys():
                    self.queue[self.host].put((self.send_gauge, [description, value, taglist]))
                else:
                    self.send_gauge(description, value, taglist)

    def _get_alerts(self, instance_id, proxy):
        # SAP_ITSAMInstance/Alert
        alerts = proxy.get_alerts(instance_id)
        for alert in alerts:
            alert_name = alert.get("AlertPath", "")
            if alert_name in Events.ccms_alerts.keys():
                lookup = Events.ccms_alerts.get(alert_name)
                description = lookup.get("description", alert_name)
                status = alert.get(lookup.get("field"), "Not specified")
                taglist = self.generate_tags(data=alert, status=status, instance_id=instance_id)
                if self.host in self.queue.keys():
                    self.queue[self.host].put((self.send_event, [description, taglist]))
                else:
                    self.send_event(description, taglist)

    def _get_proxy(self):
        # 1128 is the port of the HostControl for HTTP protocol
        host_port = "1128"
        if self.cert:
            # for HTTPS protocol, 1129 is the port of the HostControl
            host_port = "1129"
        host_control_url = "{0}:{1}/SAPHostControl".format(self.url, host_port)
        return SapProxy(host_control_url, self.user, self.password, self.verify, self.cert, self.keyfile)

    def generate_tags(self, data, status, instance_id=None, database=None):
        """
        Makes a list of tags of every whitelisted key in 'data'.\n
        Tags from the instance config are always added.\n
        'status', 'instance_id' and 'database' are always added if defined.\n
        :param data: Dict with keys and values to add to the tags
        :param status: Mandatory: Value of status tag
        :param instance_id: Optional: instance_id tag value
        :param database: Optional: database name tag value
        :return: List of tags
        """
        whitelist = []  # Tags we need
        taglist = []
        for tag in self.tags:  # self.tags contains values from
            taglist.append(tag)
        if status:
            taglist.append("status:{0}".format(status))
        if instance_id:
            taglist.append("instance_id:{0}".format(instance_id))
        if database:
            taglist.append("database:{0}".format(database))
        if data:
            for k, v in data.items():
                if k in whitelist:
                    taglist.append("{0}:{1}".format(k, v))
        return taglist

    def send_event(self, description, taglist):
        """
        Send an event based on provided data.\n
        'status' is a mandatory field in data or taglist.
        :param description: The source_type_name
        :param taglist: List of tags to append to the event
        """
        status = None
        database = None
        instance_id = None
        for tag in taglist:
            if tag.startswith("status"):
                status = tag.split(":")[1]
            elif tag.startswith("database"):
                database = tag.split(":")[1]
            elif tag.startswith("instance_id"):
                instance_id = tag.split(":")[1]
        self.event({
                "timestamp": int(time.time()),
                "source_type_name": description,
                "msg_title": "{0} status update.".format(description),
                "msg_text": status,
                "host": self.host,
                "tags": taglist
        })
        if instance_id:
            self.log.info("{0}: Send {1}={2} Event for instance ({3})".format(self.host,
                                                                              description, status, instance_id))
        elif database:
            self.log.info("{0}: Send {1}={2} Event for database ({3})".format(self.host, description, status, database))
        else:
            self.log.info("{0}: Send {1}={2} Event".format(self.host, description, status))

    def send_gauge(self, key, value, taglist):
        """
        Generate and send an gauge based on provided data.
        :param key: Use this as the name of the event
        :param value: Value to send
        :param taglist: List of tags to add
        """
#        sys.stdout.write ("name={}\nvalue={}\nhostname={}\ntags={}".format(key, value, self.host, taglist))
        self.gauge(
            name=key,
            value=value,
            tags=taglist,
            hostname=self.host
        )
        self.log.info("{0}: send {1}={2} gauge".format(self.host, key, value))

    def _collect_hosts(self):
        try:
            proxy = self._get_proxy()
            # define SAP host control component
            data = {
                "host": self.host,
                "tags": self.tags,
                "environment": self.stackstate_environment,
                "domain": self.domain
            }
            self.component(self._host_external_id(), "sap-host", data)

            host_instances = proxy.get_sap_instances()
            self.log.debug("{0}: host instances: {1}".format(self.host, host_instances))

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
                        "labels": [],
                        "domain": self.domain,
                        "environment": self.stackstate_environment,
                        "tags": self.tags
                    }
                    self.component(external_id, "sap-instance", component_data)

                    # define relation  host instance    -->    host
                    #                              is hosted on
                    source_id = external_id
                    target_id = self._host_external_id()
                    relation_data = {
                        "domain": self.domain,
                        "environment": self.stackstate_environment,
                        "tags": self.tags
                    }
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

    def _collect_instance_processes_and_metrics(self, host_instances, proxy):
        for instance_id, instance_type in list(host_instances.items()):
            try:
                # Always
                self._collect_processes(instance_id, proxy)
                if instance_type.startswith("ABAP Instance"):
                    self._collect_worker_metrics(instance_id, instance_type, proxy)
                    self._get_alerts(instance_id, proxy)
                elif instance_type.startswith("J2EE Instance"):
                    #
                    continue
                elif instance_type.startswith("Hana"):
                    # test
                    continue
                elif instance_type.startswith("Webdispatcher"):
                    #
                    continue
                elif instance_type.startswith("SAP Cloud Connector"):
                    #
                    continue
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

    def _collect_processes(self, instance_id, proxy):
        try:
            processes = proxy.get_sap_instance_processes(instance_id)
            self.log.debug("{0}: host instance '{1}' processes: {2}".format(self.host, instance_id, processes))
            if processes:
                for process in processes:
                    process_item = {i.mName: i.mValue for i in process.mProperties.item}

                    name = process_item.get("name")
                    description = process_item.get("description")
                    dispstatus = process_item.get("dispstatus")
                    textstatus = process_item.get("textstatus")
                    starttime = process_item.get("starttime")
                    elapsedtime = process_item.get("elapsedtime")
                    pid = int(process_item.get("pid"))

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
                        "labels": [],
                        "domain": self.domain,
                        "environment": self.stackstate_environment,
                        "tags": self.tags
                    }
                    self.component(external_id, "sap-process", component_data)

                    # define relation  process  -->  host instance
                    #                         runs on
                    source_id = external_id
                    target_id = self._host_instance_external_id(instance_id)
                    relation_data = {
                        "domain": self.domain,
                        "environment": self.stackstate_environment,
                        "tags": self.tags
                    }
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
        except Exception as e:
            self.log.exception(str(e))

    def _collect_worker_metrics(self, instance_id, instance_type, proxy):
        if instance_type.startswith("ABAP"):
            interesting_workers = ["DIA", "BTC"]
            try:
                num_free_workers = proxy.get_sap_instance_abap_free_workers(instance_id, interesting_workers)
                self.log.debug("{0}: number of worker processes for instance '{1}': {2}".format(
                    self.host, instance_id, num_free_workers))
                for worker_type, num_free_worker in list(num_free_workers.items()):
                    self.gauge(
                        name="{0}_workers_free".format(worker_type),
                        value=num_free_worker,
                        tags=["instance_id:{0}".format(instance_id)],
                        hostname=self.host
                    )
            except Exception as e:
                self.log.exception(str(e))

    def _collect_databases(self, proxy):
        databases = proxy.get_databases()
        self.log.debug("{0}: databases: {1}".format(self.host, databases))

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
                    "labels": [],
                    "domain": self.domain,
                    "environment": self.stackstate_environment,
                    "tags": self.tags
                }
                self.component(external_id, "sap-database", component_data)

                # define relation  database    -->    host
                #                          is hosted on
                source_id = external_id
                target_id = self._host_external_id()
                relation_data = {
                    "domain": self.domain,
                    "environment": self.stackstate_environment,
                    "tags": self.tags
                }
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
                try:
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
                            "labels": [],
                            "domain": self.domain,
                            "environment": self.stackstate_environment,
                            "tags": self.tags
                        }
                        self.component(database_component_external_id, "sap-database-component",
                                       database_component_data)

                        # define relation between database component  -->  database
                        #                                           runs on
                        database_component_relation_source_id = database_component_external_id
                        database_component_relation_target_id = external_id
                        database_component_relation_data = {
                            "domain": self.domain,
                            "environment": self.stackstate_environment,
                            "tags": self.tags
                        }
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
                                "database_name:{0}".format(database_name),
                                "database_component_name:{0}".format(database_component_name)
                            ]
                        })
                except Exception as e:
                    self.log.info("-------> No database components on host {0} database {1} :".format(self.host,
                                                                                                      database_name))
                    self.log.exception(str(e))

    def _collect_sapcloudconnector(self):
        #
        #  Uses monitoring API:
        # https://help.sap.com/viewer/cca91383641e40ffbe03bdc78f00f681/Cloud/en-US/f6e7a7bc6af345d2a334c2427a31d294.html
        #
        #  Configuring : Make port 8443 available. add this to users.xml and restart SCC.
        #
        #  <user username="<username from yml>" password="<password from yml as SHA-256 hash>" roles="sccmonitoring"/>
        #
        cloud_connector_url = "{0}:{1}/".format(self.url, "8443").replace("http://", "https://")
        self.log.debug("{0}: Trying to connect to sapcloudconnector on url: {1}".format(self.host, cloud_connector_url))
        health_url = cloud_connector_url + "exposed?action=ping"
        #
        #   1 second timeout to connect, 30 to read data.
        #
        status_code = 0
        session = Session()
        session.auth = HTTPBasicAuth(self.user, self.password)
        session.timeout = (1, 30)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            health = session.get(cloud_connector_url)
            status_code = health.status_code
        except Exception:
            self.log.debug("{0}: No SAP Cloud connector found on url: {1}".format(self.host, health_url))
            status_code = 500

        if status_code == 200:
            self.log.info("{0}: Got health from cloud connector on url: {1}".format(self.host, health_url))

            external_id = str(self._scc_external_id())
            component_data = {
                "name": "SCC",
                "description": "SAP Cloud Connector",
                # "type": "SAP Cloud Connector",
                # "sid": "SCC",
                "host": self.host,
                # "system_number": "99",
                # "version": "v1",
                "domain": self.domain,
                "environment": self.stackstate_environment,
                "tags": self.tags
                # "labels": []
            }
            self.log.debug("{0}: -----> component_data : {1}".format(self.host, component_data))
            self.log.debug("{0}: -----> external_id : {1}".format(self.host, external_id))
            self.component(external_id, "sap-cloud-connector", component_data)

            # define relation  cloud connector    -->    host
            #                          is hosted on
            source_id = external_id
            target_id = self._host_external_id()
            relation_data = {}
            self.relation(source_id, target_id, "is hosted on", relation_data)

            # define scc status event
            self.event({
                "timestamp": int(time.time()),
                "source_type_name": "SAP:scc state",
                # "source_type_name": "SAP:host instance",
                "msg_title": "SCC status update.",
                "msg_text": "",
                "host": self.host,
                "tags": [
                    "instance_id:99",
                    "status:sapcontrol-green"
                ]
            })
            #
            # Lists sub accounts to the SAP Cloud and connection tunnels
            #
            subaccount_url = cloud_connector_url + "api/monitoring/subaccounts"
            subaccount_reply = session.get(subaccount_url)
            if subaccount_reply.status_code == 200:
                reply = subaccount_reply.text.encode('utf-8')
                self.log.debug("{0}: Sub accounts reply from cloud connector : {1}".format(self.host, reply))
                subaccounts = json.loads(subaccount_reply.text)
                self.log.debug("{0}: JSON sub accounts from cloud connector : {1}".format(self.host, subaccounts))
                for subaccount in subaccounts["subaccounts"]:
                    self.log.debug("{0}: subaccount: {1}".format(self.host, subaccount))
                    # define cloud connector component
                    subaccount_name = str(subaccount.get("displayName"))
                    # display name is not always setup
                    if subaccount_name == "None":
                        subaccount_name = str(subaccount.get("subaccount"))
                    external_id = str(self._scc_subaccount_external_id(subaccount.get("subaccount")))
                    tunnel = subaccount.get("tunnel")

                    component_data = {
                        "name": subaccount_name,
                        "description": str(subaccount.get("description")),
                        "state": str(tunnel.get("state")),
                        "connectedSince": str(tunnel.get("connectedSince")),
                        "connections": str(tunnel.get("connections")),
                        "user": str(tunnel.get("user")),
                        "regionHost": str(subaccount.get("regionHost")),
                        "subaccount": str(subaccount.get("subaccount")),
                        "locationID": str(subaccount.get("locationID")),
                        "layer": "SAP SCC Sub Accounts",
                        "domain": self.domain,
                        "environment": self.stackstate_environment,
                        "host": self.host,
                        "tags": self.tags
                        # "labels": []
                    }
                    self.log.debug("{0}: -----> component_data : {1}".format(self.host, component_data))
                    self.log.debug("{0}: -----> external_id : {1}".format(self.host, external_id))
                    self.component(external_id, "sap-scc-subaccount", component_data)

                    # define relation  cloud connector    -->    host
                    #                          is hosted on
                    source_id = external_id
                    target_id = self._scc_external_id()
                    relation_data = {}
                    self.relation(source_id, target_id, "is_setup_on", relation_data)

                    # define cloud connector status event

                    tunnel_status = self._scc_subaccount_status(tunnel.get("state"))
                    self.event({
                        "timestamp": int(time.time()),
                        "source_type_name": "SAP:scc subaccount state",
                        "msg_title": "SAP Cloud Connector '{0}' status update.".format(subaccount_name),
                        "msg_text": "",
                        "host": self.host,
                        "tags": [
                            "status:{0}".format(tunnel_status),
                            "subaccount_name:{0}".format(subaccount_name)
                        ]
                    })
            else:
                if subaccount_reply.status_code == 400:
                    msg = "{0}: SAP Cloud connector monitoring sub account page not " \
                          "supported in this version of SCC.".format(self.host)
                    self.log.info(msg)
                else:
                    status = subaccount_reply.status_code
                    self.log.error("{0}: No SAP Cloud connector sub account found. Status code: {1}".format(self.host,
                                                                                                            status))
            #
            #   List backend SAP systems and virtual names.
            #
            backends_url = cloud_connector_url + "api/monitoring/connections/backends"
            backends_reply = session.get(backends_url)
            if backends_reply.status_code == 200:
                reply = backends_reply.text.encode('utf-8')
                self.log.debug("{0}: Backends reply from cloud connector : {1}".format(self.host, reply))
                backends = json.loads(backends_reply.text)
                self.log.info("{0}: JSON backends from cloud connector : {1}".format(self.host, backends))
                for subaccount in backends["subaccounts"]:
                    # subaccount["regionHost"]
                    # subaccount["subaccount"]
                    # subaccount["locationID"]
                    virtualbackend = str(subaccount.get("virtualBackend"))
                    for backend in subaccount["backendConnections"]:
                        external_id = self._scc_backend_external_id(subaccount["subaccount"], virtualbackend)
                        component_data = {
                            "virtualBackend": virtualbackend,
                            "internalBackend": str(backend.get("internalBackend")),
                            "protocol": str(backend.get("protocol")),
                            "idle": str(backend.get("idle")),
                            "active": str(backend.get("active")),
                            "labels": [],
                            "layer": "SAP SCC Back-ends",
                            "domain": self.domain,
                            "environment": self.stackstate_environment,
                            "tags": self.tags
                        }
                        self.log.debug("{0}: ------> external_id : {1}".format(self.host, external_id))
                        self.component(external_id, "sap-cloud", component_data)
                        # define relation  cloud connector    -->    host
                        #                          is hosted on
                        source_id = external_id
                        target_id = self._scc_subaccount_external_id(subaccount["subaccount"])
                        relation_data = {}
                        self.relation(source_id, target_id, "is connected to", relation_data)
                        self.event({
                            "timestamp": int(time.time()),
                            "source_type_name": "SAP:cloud component state",
                            "msg_title": "SAP Cloud Connector '{0}' status update.".format(backend["virtualBackend"]),
                            "msg_text": "",
                            "host": self.host,
                            "tags": [
                                "active:{0}".format(backend["active"]),
                                "idle:{0}".format(backend["idle"])
                            ]
                        })
            else:
                if backends_reply.status_code == 400:
                    msg = "{0}: SAP Cloud connector monitoring backend page not supported " \
                          "in this version of SCC.".format(self.host)
                    self.log.info(msg)
                else:
                    status = backends_reply.status_code
                    self.log.error("{0}: No SAP Cloud connector backends found. Status code: {1}".format(self.host,
                                                                                                         status))
        if status_code == 401:
            msg = "{0}: Authentication failed, check your config.yml and SCC users.xml " \
                  "for corresponding username and password.".format(self.host)
            self.log.error(msg)
        session.close()

    def _collect_saprouter(self, proxy):
        """
        Discovers if OS process saprouter is running.
        :param proxy: proxy object
        """
        results = proxy.get_cim_object("EnumerateInstances", "SAP_ITSAMOSProcess?CommandLine=*saprouter*")
        # self.log.info("{0}:----------->  results: {1}".format(self.host,results))
        if results:
            for result in results:
                # self.log.info("{0}:----------->  result: {1}".format(self.host,result))
                data = {i.mName: i.mValue for i in result.mProperties.item}
                external_id = self._saprouter_external_id(data.get("PID"))
                component_data = {
                        "name": data.get("Name"),
                        "PID": data.get("PID"),
                        "CommandLine": data.get("CommandLine"),
                        "Username": data.get("Username"),
                        "layer": "Processes",
                        "domain": self.domain,
                        "environment": self.stackstate_environment,
                        "host": self.host,
                        "tags": self.tags
                        # "labels": []
                    }
                self.component(external_id, "sap-saprouter", component_data)

                # define relation  saprouter    -->    host
                #                          runs on
                source_id = external_id
                target_id = self._host_external_id()
                relation_data = {}
                self.relation(source_id, target_id, "runs_on", relation_data)

                # define cloud connector status event
                self.event({
                    "timestamp": int(time.time()),
                    "source_type_name": "SAP:saprouter state",
                    "msg_title": "SAP Router '{0}' status update.".format(data.get("PID")),
                    "msg_text": "",
                    "host": self.host,
                    "tags": [
                        "status:OK",
                        "PID:{0}".format(data.get("PID"))
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

    def _scc_external_id(self):
        return "urn:sap:/scc:{0}".format(self.host)

    def _scc_subaccount_external_id(self, subaccount):
        return "urn:sap:/scc_subaccount:{0}:{1}".format(self.host, subaccount)

    def _scc_backend_external_id(self, subaccount, virtual_backend):
        return "urn:sap:/scc_backend:{0}:{1}:{2}".format(self.host, subaccount, virtual_backend)

    def _saprouter_external_id(self, pid):
        return "urn:sap:/saprouter:{0}:{1}".format(self.host, pid)

    def _scc_subaccount_status(self,  status):
        switcher = {
                "Connected": "sapcontrol-green",
                "ConnectFailure": "sapcontrol-red"
            }
        return switcher.get(status, "Unknown status")
