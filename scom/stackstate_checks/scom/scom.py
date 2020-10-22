from requests import Session
import base64
from requests_ntlm import HttpNtlmAuth
import time
import re
import json
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance
import subprocess

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

    def get_type(self,session,component_id,domain, username, password, scom_ip):
        if self.requests_counter > self.requests_threshold:
           return
        type_data = {
                                "criteria": "(Id = '"+component_id+"')"
                                }
        type_response = (session.post('http://'+ scom_ip +'/OperationsManager/data/scomObjects',auth=HttpNtlmAuth(domain + '\\' + username, password),json=type_data["criteria"])).json()
        self.requests_counter +=1
        self.log.debug("Number of requets: "+str(self.requests_counter))
        component_type = type_response.get("scopeDatas")[0].get("className").lower().replace(" ","-")
        return str(component_type)

    def get_component_data_and_relations(self,session,component_id, domain, username, password, scom_ip):
        if self.requests_counter > self.requests_threshold:
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
        type = self.get_type(session,component_id,domain, username, password, scom_ip)
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
               self.get_component_data_and_relations(session,relation.get("id"), domain, username, password, scom_ip)

    def scom_api_check(self,streams,auth_method, domain, username, password, scom_ip):
        session = Session()
        self.log.info('Connection Status Code ' + self.init_session(session, auth_method, domain, username, password, scom_ip))
        for stream in streams:
            data = {
                        "fullClassName": "" + stream.get('class') + ""
                    }
            response = (session.post('http://' + scom_ip + '/OperationsManager/data/scomObjectsByClass',auth=HttpNtlmAuth(domain + '\\' + username, password),json=data["fullClassName"])).json()
            root_tree = response.get("rows", [])
            for component in root_tree:
                self.get_component_data_and_relations(session,component["id"], domain, username, password, scom_ip)

    def excute_powershell_cmd(self,scom_server,cmd):
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
    def scom_powershell_check(self,scom_server):
        components = self.excute_powershell_cmd (scom_server,"C:\\ProgramData\\StackState\\conf.d\\scom.d\\components.ps1")
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
        relations = self.excute_powershell_cmd (scom_server,"C:\\ProgramData\\StackState\\conf.d\\scom.d\\relations.ps1")
        for rel in relations:
            source_id = str(rel["source"]["Id"])
            target_id = str(rel["target"]["Id"])
            self.relation(source_id,target_id,"Is_connected_to",{})

    def check(self, instance):
        scom_ip = str(instance.get('hostip'))
        domain = str(instance.get('domain'))
        username = str(instance.get('username'))
        password = str(instance.get('password'))
        auth_method = str(instance.get('auth_mode'))
        integration_mode = str(instance.get('integration_mode'))
        self.requests_threshold = instance.get('max_number_of_requests')
        streams = instance.get('streams')
        # read configuration file/yaml configuration
        self.start_snapshot()
        if integration_mode == 'api':
           self.scom_api_check(streams,auth_method, domain, username, password, scom_ip)
        else:
           self.scom_powershell_check(scom_ip)
        self.log.info("maximum number of requests reached! "+str(self.requests_counter))
        self.requests_counter = 0
