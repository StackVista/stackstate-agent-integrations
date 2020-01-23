# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Transport


class SapProxy(object):

    def __init__(self, url, user, password):
        session = Session()
        session.auth = HTTPBasicAuth(user, password)
        wsdl_url = "{0}/?wsdl".format(url)
        self.client = Client(wsdl_url, transport=Transport(session=session, timeout=10))

    def get_databases(self):
        """Retrieves all databases with their components from the host control"""

        # ns0:ArrayOfProperty(item: ns0:Property[])
        properties_type = self.client.get_type("ns0:ArrayOfProperty")
        properties = properties_type()

        # ListDatabases(aArguments: ns0:ArrayOfProperty) -> result: ns0:ArrayOfDatabase
        return self.client.service.ListDatabases(properties)

    def get_sap_instances(self):
        """Retrieves all SAP instances from the host control"""

        # ns0:Property(mKey: xsd:string, mValue: xsd:string)
        property_type = self.client.get_type("ns0:Property")
        sap_instance_property = property_type(mKey="EnumerateInstances", mValue="SAPInstance")

        # ns0:ArrayOfProperty(item: ns0:Property[])
        properties_type = self.client.get_type("ns0:ArrayOfProperty")
        properties = properties_type([sap_instance_property])

        # GetCIMObject(aArguments: ns0:ArrayOfProperty) -> result: ns0:ArrayOfCIMObject
        return self.client.service.GetCIMObject(properties)

    def get_sap_instance_processes(self):
        """Retrieves all processes on a host instance"""

        # GetProcessList() -> process: ns0:ArrayOfOSProcess
        return self.client.service.GetProcessList()

    def get_sap_instance_abap_free_workers(self):
        """Retrieves free workers metric from an ABAP host instance"""

        # ABAPGetWPTable() -> workprocess: ns0:ArrayOfWorkProcess
        worker_processes = self.client.service.ABAPGetWPTable()

        grouped_workers = {}
        for worker in worker_processes:
            grouped_workers[worker.Typ] = grouped_workers.get(worker.Typ, []) + [(worker.Pid, worker.Status)]

        num_free_workers = {}
        for worker_type in ["DIA", "BTC"]:
            typed_workers = grouped_workers.get(worker_type, [])
            free_typed_workers = [worker for worker in typed_workers if worker[1].lower() == "wait"]
            num_free_workers.update({worker_type: len(free_typed_workers)})

        return num_free_workers

    def get_sap_instance_physical_memory(self):
        """Retrieves physical memory (in megabytes) metric from an host instance"""

        # ParameterValue(parameter: xsd:string) -> value: xsd:string
        return self.client.service.ParameterValue(parameter="PHYS_MEMSIZE")
