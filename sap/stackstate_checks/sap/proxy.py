# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Transport
import base64
from time import time

class SapProxy(object):

    _alerts = {}

    def __init__(self, url, user, password, verify=True, cert=None, keyfile=None, cache_ttl=None):
        session = Session()
        if cert:
            session.verify = verify
            session.cert = (cert, keyfile)
        else:
            session.auth = HTTPBasicAuth(user, password)
        wsdl_url = "{0}/?wsdl".format(url)
        self.client = Client(wsdl_url, transport=Transport(session=session, timeout=10))
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
        self.service = self.client.create_service("{urn:SAPHostControl}SAPHostControl", address+"/SAPHostControl.cgi")


    def get_alerts(self, instance_id):
        """
        Get all/any alerts for instance_id that match key and value.
        :param instance_id: ID of SAP instance on host
        :return: List with dict for every match. May be an empty list
        """
        query = "SAP_ITSAMInstance/Alert??Instancenumber={}".format(instance_id)
        return self.get_cim_object("EnumerateInstances", query)


    def get_computerSystem(self):
        """
        Get most important statistics about computer, os , processor, network and filesystem
        """

        # ns0:ArrayOfProperty(item: ns0:Property[])
        properties_type = self.client.get_type("ns0:ArrayOfProperty")
        properties = properties_type()

        # ListDatabases(aArguments: ns0:ArrayOfProperty) -> result: ns0:ArrayOfDatabase
        return self.service.GetComputerSystem(properties)


    def get_databases(self):
        """Retrieves all databases with their components from the host control"""

        # ns0:ArrayOfProperty(item: ns0:Property[])
        properties_type = self.client.get_type("ns0:ArrayOfProperty")
        properties = properties_type()

        # ListDatabases(aArguments: ns0:ArrayOfProperty) -> result: ns0:ArrayOfDatabase
        return self.service.ListDatabases(properties)


    def get_sap_instances(self):
        """Retrieves all SAP instances from the host control"""
        return self.get_cim_object("EnumerateInstances", "SAPInstance")


    def get_sap_instance_processes(self, instance_id):
        """Retrieves all processes on a host instance"""
        query = "SAP_ITSAMInstance/Process??Instancenumber={0}".format(instance_id)
        return self.get_cim_object("EnumerateInstances", query)


    def get_sap_instance_abap_free_workers(self, instance_id, worker_types):
        """Retrieves free workers metric from an ABAP host instance"""
        query = "SAP_ITSAMInstance/WorkProcess??Instancenumber={0}".format(instance_id)
        worker_processes = self.get_cim_object("EnumerateInstances", query)
        if worker_processes:
            grouped_workers = {}
            for worker_proces in worker_processes:
                worker_proces_item = {i.mName: i.mValue for i in worker_proces.mProperties.item}
                typ = worker_proces_item.get("Typ")
                status = worker_proces_item.get("Status")
                pid = worker_proces_item.get("Pid")
                grouped_workers[typ] = grouped_workers.get(typ, []) + [(pid, status)]

            num_free_workers = {}
            for worker_type in worker_types:
                typed_workers = grouped_workers.get(worker_type, [])
                free_typed_workers = [worker for worker in typed_workers if worker[1].lower() == "wait"]
                num_free_workers.update({worker_type: len(free_typed_workers)})

        return num_free_workers


    def get_sap_instance_params(self, instance_id):
        """Retrieves SAP instance parameters from an host instance as a key value pair"""
        query = "SAP_ITSAMInstance/Parameter??Instancenumber={0}".format(instance_id)
        params_reply = self.get_cim_object("EnumerateInstances", query)
        if params_reply:
            for param_reply in params_reply:
                params_item = {i.mName: i.mValue for i in param_reply.mProperties.item}
                base64parameters = params_item.get("value")
                base64decodedparams = base64.b64decode(base64parameters)
                params = {}
                line_params = base64decodedparams.split(b'\n')
                for line in line_params:
                    name, var = line.partition(b'=')[::2]
                    params[name.decode()] = var.decode()

        return params


    def get_cim_object(self, key, value):
        # ns0:Property(mKey: xsd:string, mValue: xsd:string)
        property_type = self.client.get_type("ns0:Property")
        sap_instance_property = property_type(mKey=key, mValue=value)

        # ns0:ArrayOfProperty(item: ns0:Property[])
        properties_type = self.client.get_type("ns0:ArrayOfProperty")
        properties = properties_type([sap_instance_property])

        return self.service.GetCIMObject(properties)
