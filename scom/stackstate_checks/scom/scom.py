from requests import Session
import base64
from requests_ntlm import HttpNtlmAuth
import time
import re
from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse


def init_session(session, auth_method, domain, username, password, scom_ip):
    request_credentials = base64.b64encode(auth_method + ':' + domain + '\\' + username + ':' + password)
    response = session.post('http://' + scom_ip + '/OperationsManager/authenticate',
                            auth=HttpNtlmAuth(domain + '\\' + username, password), json=request_credentials)
    return str(response.status_code)


def hasChild(serviceid, session, scom_ip, domain, username, password):
    response = (session.get('http://' + scom_ip + '/OperationsManager/data/objectInformation/' + serviceid,
                            auth=HttpNtlmAuth(domain + '\\' + username, password))).json()
    service_data_tree = response.get("relatedObjects", [])
    if not service_data_tree:
        return False
    else:
        return True


def get_entity_health_state(session, scom_ip, domain, username, password, healthIconUrl):
    if re.search('StatusOkComplete', healthIconUrl, flags=re.IGNORECASE) or re.search('healthy_ex', healthIconUrl,
                                                                                      flags=re.IGNORECASE):
        return 'Healthy'
    elif re.search('StatusWarning', healthIconUrl, flags=re.IGNORECASE) or re.search('warning_ex', healthIconUrl,
                                                                                     flags=re.IGNORECASE):
        return 'Deviating'
    elif re.search('StatusError', healthIconUrl, flags=re.IGNORECASE) or re.search('critical_ex', healthIconUrl,
                                                                                   flags=re.IGNORECASE):
        return 'Error'
    elif re.search('StatusUnknownGreen', healthIconUrl, flags=re.IGNORECASE) or re.search('maintenance_ex',
                                                                                          healthIconUrl,
                                                                                          flags=re.IGNORECASE):
        return 'Not Monitored'
    else:
        return 'Unkown'


class SCOM(AgentCheck):
    INSTANCE_TYPE = 'scom'

    def get_instance_key(self, instance):
        if 'hostip' not in instance:
            raise ConfigurationError('Missing url in topology instance configuration.')

        instance_url = instance['hostip']
        return TopologyInstance(self.INSTANCE_TYPE, instance_url, with_snapshots=False)

    def sendAlerts(self, session, scom_ip, domain, username, password, component_id):
        data = {
            "criteria": "(MonitoringObjectId = '" + component_id + "')",
            "displayColumns":
                [
                    "id", "name", "monitoringobjectdisplayname", "description", "resolutionstate", "timeadded",
                    "monitoringobjectpath"
                ]
        }
        response = (session.post('http://' + scom_ip + '/OperationsManager/data/alert',
                                 auth=HttpNtlmAuth(domain + '\\' + username, password), json=data)).json()
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

    def getComponentDetails(self, id, session, scom_ip, domain, username, password):
        response = (session.get('http://' + scom_ip + '/OperationsManager/data/objectInformation/' + id,
                                auth=HttpNtlmAuth(domain + '\\' + username, password))).json()
        data = response.get("monitoringObjectProperties", [])
        list = dict()
        for detail in data:
            list.update({str(detail.get("name").encode('utf-8')):str(detail.get("value").encode('utf-8'))})
        return list

    def nextNodes(self, serviceid, session, scom_ip, domain, username, password, system_type):
        ids = []
        response = (session.get('http://' + scom_ip + '/OperationsManager/data/objectInformation/' + serviceid,
                                auth=HttpNtlmAuth(domain + '\\' + username, password))).json()
        data = response.get("relatedObjects", [])
        for idd in data:
            ids.append(idd.get("id"))
            dataA = {"name": str(idd.get("displayName")),
                     "id": str(idd.get("id")),
                     "domain": system_type,
                     "labels": [
                         system_type
                     ]
                     }
            dataB = self.getComponentDetails(idd.get("id"), session, scom_ip, domain, username, password)
            dataA.update(dataB)
            self.component(str(idd.get("id")), str(system_type + "_component"), dataA)
            self.event({
                "timestamp": int(time.time()),
                "msg_title": "Health Status",
                "msg_text": "Change in health status",
                "source_type_name": "Health",
                "host": idd.get("displayName"),
                "tags": [
                    "status:%s" % get_entity_health_state(session, scom_ip, domain, username, password,
                                                          idd.get("healthIconUrl")),
                    "id:%s" % idd.get("id")
                ]
            })
            self.relation(str(serviceid), str(idd.get("id")), "hosted_on", {})
            self.sendAlerts(session, scom_ip, domain, username, password, idd.get("id"))
        return ids

    def serviceTree(self, serviceidtree, session, scom_ip, domain, username, password, system_type):
        for serviceid in serviceidtree:
            if not hasChild(serviceid, session, scom_ip, domain, username, password):
                continue
            else:
                self.serviceTree(self.nextNodes(serviceid, session, scom_ip, domain, username, password, system_type),
                                 session, scom_ip, domain, username, password, system_type)

    def check(self, instance):
        # read configuration file/yaml configuration
        scom_ip = str(instance.get('hostip'))
        domain = str(instance.get('domain'))
        username = str(instance.get('username'))
        password = str(instance.get('password'))
        auth_method = str(instance.get('auth_mode'))
        streams = instance.get('streams')
        session = Session()
        self.log.info(
            'Connection Status Code ' + init_session(session, auth_method, domain, username, password, scom_ip))
        # topology_instance_key = {"type": "scom", "url": scom_ip}
        try:
            self.start_snapshot()
            for stream in streams:
                data = {
                    "fullClassName": "" + stream.get('class') + ""
                }
                response = (session.post('http://' + scom_ip + '/OperationsManager/data/scomObjectsByClass',
                                         auth=HttpNtlmAuth(domain + '\\' + username, password),
                                         json=data["fullClassName"])).json()
                root_ids = []
                root_tree = response.get("rows", [])
                for component in root_tree:
                    dataA = {"name": str(component.get("displayname")),
                             "id": str(component.get("id")),
                             "domain": str(stream.get('name')),
                             "labels": [
                                 str(stream.get('name'))
                             ]
                             }
                    dataB = self.getComponentDetails(component.get("id"), session, scom_ip, domain, username, password)
                    dataA.update(dataB)
                    self.component(str(component.get("id")), str(stream.get('name') + "_component"), dataA)
                    health = session.get(
                        'http://' + scom_ip + '/OperationsManager/data/healthstate/' + component.get("id", None),
                        auth=HttpNtlmAuth(domain + '\\' + username, password))
                    self.event({
                        "timestamp": int(time.time()),
                        "msg_title": "Health Status",
                        "msg_text": "Change in health status",
                        "source_type_name": "Health",
                        "host": component.get("displayname"),
                        "tags": [
                            "status:%s" % get_entity_health_state(session, scom_ip, domain, username, password,
                                                                  health.text),
                            "id:%s" % component.get("id")
                        ]
                    })
                    self.sendAlerts(session, scom_ip, domain, username, password, component.get("id"))
                    root_ids.append(component.get("id"))
                self.serviceTree(root_ids, session, scom_ip, domain, username, password, stream.get('name'))
            self.stop_snapshot()
            self.service_check("scom", AgentCheck.OK, message="SCOM synchronized successfully")
            session.close()
        except Exception as e:
            self.log.exception("SCOM Error: %s" % str(e))
            session.close()
            self.service_check("scom", AgentCheck.CRITICAL, message=str(e))
            raise e  # CheckException("SCOM Error: %s" % e), None, sys.exc_info()[2]
