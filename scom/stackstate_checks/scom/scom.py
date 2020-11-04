from requests import Session
import base64
from requests_ntlm import HttpNtlmAuth
import time
import re
import json
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance
import subprocess
import os.path
class SCOM(AgentCheck):

    INSTANCE_TYPE = 'scom'
    requests_counter = 0
    def get_instance_key(self, instance):
        if 'hostip' not in instance:
            raise ConfigurationError('Missing url in topology instance configuration.')

        instance_url = instance['hostip']
        return TopologyInstance(self.INSTANCE_TYPE, instance_url)

    def init_session(self,session, auth_method, domain, username, password, scom_ip):
        request_credentials = base64.b64encode(auth_method + ':' + domain + '\\' + username + ':' + password)
        response = session.post('http://' + scom_ip + '/OperationsManager/authenticate',auth=HttpNtlmAuth(domain + '\\' + username, password), json=request_credentials)
        return str(response.status_code)

    def send_alerts(self, session,component_id, domain, username, password, scom_ip):
        if self.requests_counter > self.requests_threshold:
           session.close()
           return
        data = {
            "criteria": "(MonitoringObjectId = '" + component_id + "')",
            "displayColumns":
                [
                    "id", "name", "monitoringobjectdisplayname", "description", "resolutionstate", "timeadded",
                    "monitoringobjectpath"
                ]
        }
        response = (session.post('http://' + scom_ip + '/OperationsManager/data/alert',auth=HttpNtlmAuth(domain + '\\' + username, password), json=data)).json()
        self.requests_counter += 1
        self.log.debug("Number of requets: "+str(self.requests_counter))
        events_data_tree = response.get("rows", [])
        for event in events_data_tree:
            self.event({
                "timestamp": int(time.time()),
                "msg_title": event.get("name"),
                "msg_text": event.get("description"),
                "source_type_name": "Alert",
                "host": event.get("monitoringobjectdisplayname"),
                "tags": [
                    "id:%s" % component_id,
                    "server:%s" % event.get("monitoringobjectpath"),
                    "resolution_state:%s" % event.get("resolutionstate"),
                    "time_added:%s" % event.get("timeadded")
                ]
            })
    def get_health_state(self,healthIconUrl):
        if re.search('StatusOkComplete', healthIconUrl, flags=re.IGNORECASE) or re.search('healthy_ex', healthIconUrl,flags=re.IGNORECASE):
           return 'Healthy'
        elif re.search('StatusWarning', healthIconUrl, flags=re.IGNORECASE) or re.search('warning_ex', healthIconUrl,flags=re.IGNORECASE):
           return 'Deviating'
        elif re.search('StatusError', healthIconUrl, flags=re.IGNORECASE) or re.search('critical_ex', healthIconUrl,flags=re.IGNORECASE):
           return 'Error'
        elif re.search('StatusUnknownGreen', healthIconUrl, flags=re.IGNORECASE) or re.search('maintenance_ex',healthIconUrl,flags=re.IGNORECASE):
           return 'Not Monitored'
        else:
           return str(healthIconUrl.split("/")[-1])

    def get_component_data_and_relations(self,session,component_id, domain, username, password, scom_ip,types_dict):
        if self.requests_counter > self.requests_threshold:
           session.close()
           return
        response = (session.get('http://' + scom_ip + '/OperationsManager/data/objectInformation/' + component_id, auth=HttpNtlmAuth(domain + '\\' + username, password))).json()
        self.requests_counter +=1
        self.log.debug("Number of requets: "+str(self.requests_counter))
        properties = response.get("monitoringObjectProperties", [])
        relations = response.get("relatedObjects", [])
        properties_list = dict()
        relations_list = []
        for detail in properties:
            properties_list.update({str(detail.get("name").encode('utf-8')):str(detail.get("value").encode('utf-8'))})
        name = str(response["displayName"])
        properties_list.update({"id":str(component_id),"name":name})
        health = self.get_health_state(response["healthIconUrl"])
        type = str(types_dict.get(component_id)).encode('utf-8')
        self.component(str(component_id),type, properties_list)
        self.event({
                "timestamp": int(time.time()),
                "msg_title": "Health Status",
                "msg_text": "Change in health status",
                "source_type_name": "Health",
                "host": name,
                "tags": [
                    "status:%s" % health,
                    "id:%s" % str(component_id)
                ]
            })
        self.send_alerts(session,component_id, domain, username, password, scom_ip)
        if relations:
           for relation in relations:
               self.relation(str(component_id),relation.get("id"),"is_connected_to",{})
               self.get_component_data_and_relations(session,relation.get("id"), domain, username, password, scom_ip,types_dict)

    def scom_api_check(self,criteria,auth_method, domain, username, password, scom_ip):
        session = Session()
        self.log.info('Connection Status Code ' + self.init_session(session, auth_method, domain, username, password, scom_ip))
        types_dict = dict()
        type_response = (session.post('http://' + scom_ip + '/OperationsManager/data/scomObjects',auth=HttpNtlmAuth(domain + '\\' + username, password), json="(Id LIKE '%')")).json()
        types = type_response.get("scopeDatas", [])
        for item in types:
            types_dict.update({str(item.get("id")): str(item.get("className")).lower().replace(" ", "-")})
        component_ids_response = (session.post('http://' + scom_ip + '/OperationsManager/data/scomObjects',auth=HttpNtlmAuth(domain + '\\' + username, password), json=criteria)).json()
        if component_ids_response.get("errorMessage"):
           #print("Invalid criteria :" + str(component_ids_response.get("errorMessage")))
           self.log.error("Invalid criteria :" + str(component_ids_response.get("errorMessage")))
        else:
           component_ids = component_ids_response.get("scopeDatas", [])
           for component in component_ids:
               self.get_component_data_and_relations(session,component.get("id"), domain, username, password, scom_ip,types_dict)
        session.close()

    def excute_powershell_cmd(self,scom_server,cmd, ps1):
        if ps1:
           dir_path = os.path.dirname(os.path.abspath(__file__))
           cmd = os.path.join(dir_path, cmd)
        excute_command = subprocess.Popen(["powershell.exe","Start-OperationsManagerClientShell -managementServerName "+scom_server+" \n",cmd],stdout=subprocess.PIPE)
        output = excute_command.communicate()[0]
        excute_command.terminate()
        result = json.loads(output)
        return result
    def get_health_powershell(self,health):
        if health == 0:
            return 'Not Monitored'
        elif health == 1:
            return 'Healthy'
        elif health == 2:
            return 'Deviating'
        elif health == 3:
            return 'Error'
        else:
            return str(health)
    def send_alerts_powershell(self,scom_server):
        events = self.excute_powershell_cmd(scom_server,"Get-SCOMAlert | select \"monitoringobjectid\", \"name\", \"monitoringobjectdisplayname\", \"description\", \"resolutionstate\", \"monitoringobjectpath\" -ExpandProperty  timeadded| ConvertTo-Json \n", False)
        for event in events:
            self.event({
                "timestamp": int(time.time()),
                "msg_title": event.get("Name"),
                "msg_text": event.get("Description"),
                "source_type_name": "Alert",
                "host": event.get("MonitoringObjectDisplayName"),
                "tags": [
                    "id:%s" % event.get("MonitoringObjectId"),
                    "server:%s" % event.get("MonitoringObjectPath"),
                    "resolution_state:%s" % event.get("ResolutionState"),
                    "time_added:%s" % event.get("DateTime")
                ]
            })
    def scom_powershell_check(self,scom_server):
        components = self.excute_powershell_cmd(scom_server,"components.ps1",True)
        for cmp in components:
            properties_list = dict()
            for key,value in cmp.items():
                properties_list.update({str(key).encode('utf-8'):str(value).encode('utf-8')})
            name = str(cmp["DisplayName"])
            component_id =  str(cmp["Id"])
            health = self.get_health_powershell(cmp["HealthState"])
            component_type = str(cmp["FullName"].lower().split(":")[0])
            properties_list.update({"id":str(component_id),"name":name})
            self.component(component_id,component_type,properties_list)
            self.event({
                "timestamp": int(time.time()),
                "msg_title": "Health Status",
                "msg_text": "Change in health status",
                "source_type_name": "Health",
                "host": name,
                "tags": [
                    "status:%s" % health,
                    "id:%s" % str(component_id)
                ]
            })
        relations = self.excute_powershell_cmd(scom_server,"relations.ps1",True)
        for rel in relations:
            source_id = str(rel["source"]["Id"])
            target_id = str(rel["target"]["Id"])
            self.relation(source_id,target_id,"Is_connected_to",{})
        self.send_alerts_powershell(scom_server)
    def check(self, instance):
        scom_ip = str(instance.get('hostip'))
        domain = str(instance.get('domain'))
        username = str(instance.get('username'))
        password = str(instance.get('password'))
        auth_method = str(instance.get('auth_mode'))
        integration_mode = str(instance.get('integration_mode', 'api'))
        self.requests_threshold = instance.get('max_number_of_requests', 5000)
        criteria = instance.get('criteria')
        # read configuration file/yaml configuration
        try:
            self.start_snapshot()
            if integration_mode == 'api':
               self.scom_api_check(criteria,auth_method, domain, username, password, scom_ip)
            else:
               self.scom_powershell_check(scom_ip)
            if self.requests_counter > self.requests_threshold:
               self.log.info("maximum number of requests reached! "+str(self.requests_counter))
            else:
               self.log.info("Total number of requests: "+str(self.requests_counter))
            self.requests_counter = 0
        except Exception as e:
            self.stop_snapshot()
            self.log.exception("SCOM Error: %s" % str(e))
            self.service_check("scom", AgentCheck.CRITICAL, message=str(e))
            raise e
