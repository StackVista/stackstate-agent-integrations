# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Transport


class SapProxy(object):

    def __init__(self, url, user, password, verify=True, cert=None, keyfile=None):
        session = Session()
        if cert:
            session.verify = verify
            session.cert = (cert, keyfile)
        session.auth = HTTPBasicAuth(user, password)
        wsdl_url = "{0}/?wsdl".format(url)
        self.client = Client(wsdl_url, transport=Transport(session=session, timeout=10))
        sap_type = wsdl_url.split("/")[-2]
        address = "/".join(wsdl_url.split("/")[:-2])
        # ServiceProxy for same host location from config as the host location can be different in WSDL response
        # As an Example -
        #
        # Case 1.) Type - SAPHostControl
        #
        #   URL = http://192.168.0.1:1128  - in case of http
        #   URL = https://192.168.0.1:1129  - in case of https
        #
        #   SOAP Address location in WSDL response is "http://18.92.32.0:1128/SAPHostControl.cgi"
        #   then creating a ServiceProxy with the given URL config, it will become
        #   "http://192.168.0.1:1128/SAPHostControl.cgi" and same goes for https

        # Case 2.) Type - SAPHostAgent
        #
        #   URL = http://192.168.0.1:50013 in case of http
        #   URL = https://192.168.0.1:50014 in case of https
        #
        #   SOAP Address location in WSDL response is "http://18.92.32.0:50013"
        #   then creating a ServiceProxy with the given URL config, it will become
        #   "http://192.168.0.1:50013" and same goes for https.

        if sap_type == "SAPHostControl":
            self.service = self.client.create_service("{urn:SAPHostControl}SAPHostControl",
                                                      address+"/SAPHostControl.cgi")
        else:
            self.service = self.client.create_service("{urn:SAPControl}SAPControl", address)

    def get_databases(self):
        """Retrieves all databases with their components from the host control"""

        # ns0:ArrayOfProperty(item: ns0:Property[])
        properties_type = self.client.get_type("ns0:ArrayOfProperty")
        properties = properties_type()

        # ListDatabases(aArguments: ns0:ArrayOfProperty) -> result: ns0:ArrayOfDatabase
        return self.service.ListDatabases(properties)

    def get_sap_instances(self):
        """Retrieves all SAP instances from the host control"""

        # ns0:Property(mKey: xsd:string, mValue: xsd:string)
        property_type = self.client.get_type("ns0:Property")
        sap_instance_property = property_type(mKey="EnumerateInstances", mValue="SAPInstance")

        # ns0:ArrayOfProperty(item: ns0:Property[])
        properties_type = self.client.get_type("ns0:ArrayOfProperty")
        properties = properties_type([sap_instance_property])

        # GetCIMObject(aArguments: ns0:ArrayOfProperty) -> result: ns0:ArrayOfCIMObject
        return self.service.GetCIMObject(properties)

    def get_sap_instance_processes(self):
        """Retrieves all processes on a host instance"""

        # GetProcessList() -> process: ns0:ArrayOfOSProcess
        return self.service.GetProcessList()

    def get_sap_instance_abap_free_workers(self, worker_types):
        """Retrieves free workers metric from an ABAP host instance"""

        # ABAPGetWPTable() -> workprocess: ns0:ArrayOfWorkProcess
        worker_processes = self.service.ABAPGetWPTable()

        grouped_workers = {}
        for worker in worker_processes:
            grouped_workers[worker.Typ] = grouped_workers.get(worker.Typ, []) + [(worker.Pid, worker.Status)]

        num_free_workers = {}
        for worker_type in worker_types:
            typed_workers = grouped_workers.get(worker_type, [])
            free_typed_workers = [worker for worker in typed_workers if worker[1].lower() == "wait"]
            num_free_workers.update({worker_type: len(free_typed_workers)})

        return num_free_workers

    def get_sap_instance_physical_memory(self):
        """Retrieves physical memory (in megabytes) metric from an host instance"""

        # ParameterValue(parameter: xsd:string) -> value: xsd:string
        return self.service.ParameterValue(parameter="PHYS_MEMSIZE")
