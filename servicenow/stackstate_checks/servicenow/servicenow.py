# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# 3rd party
import requests

# project
from stackstate_checks.base import ConfigurationError, AgentCheck, TopologyInstance

# inbuilt
import yaml


EVENT_TYPE = SOURCE_TYPE_NAME = 'servicenow'


class InstanceInfo():

    def __init__(self, instance_tags, base_url, auth):
        self.instance_tags = instance_tags
        self.base_url = base_url
        self.auth = auth


class ServicenowCheck(AgentCheck):

    INSTANCE_TYPE = "servicenow_cmdb"
    SERVICE_CHECK_NAME = "servicenow.cmdb.topology_information"

    def get_instance_key(self, instance):
        if "url" not in instance:
            raise ConfigurationError("Missing 'url' in instance configuration.")

        return TopologyInstance(self.INSTANCE_TYPE, instance["url"])

    def check(self, instance):
        if 'url' not in instance:
            raise ConfigurationError('ServiceNow CMDB topology instance missing "url" value.')
        if 'user' not in instance:
            raise ConfigurationError('ServiceNow CMDB topology instance missing "user" value.')
        if 'password' not in instance:
            raise ConfigurationError('ServiceNow CMDB topology instance missing "password" value.')

        user = instance['user']
        password = instance['password']
        auth = (user, password)

        base_url = instance['url']
        batch_size = instance['batch_size']
        instance_tags = instance.get('tags', [])

        default_timeout = self.init_config.get('default_timeout', 5)
        timeout = float(instance.get('timeout', default_timeout))

        instance_config = InstanceInfo(instance_tags, base_url, auth)

        relation_types = self._process_and_cache_relation_types(instance_config, timeout)
        try:
            self.start_snapshot()
            self._process_components(instance_config, timeout)
            self._process_component_relations(instance_config, batch_size, timeout, relation_types)
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e), tags=instance_tags)
        finally:
            self.stop_snapshot()

        # Report ServiceCheck OK
        msg = "ServiceNow CMDB instance detected at %s " % base_url
        tags = ["url:%s" % base_url]
        self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=tags, message=msg)

    def _collect_components(self, instance_config, timeout):
        """
        collect components from ServiceNow CMDB's cmdb_ci table
        (API Doc- https://developer.servicenow.com/app.do#!/rest_api_doc?v=london&id=r_TableAPI-GET)

        :return: dict, raw response from CMDB
        """

        base_url = instance_config.base_url
        auth = instance_config.auth
        url = base_url + '/api/now/table/cmdb_ci?sysparm_fields=name,sys_id,sys_class_name,sys_created_on'

        return self._get_json(url, timeout, auth)

    def _process_components(self, instance_config, timeout):
        """
        process components fetched from CMDB
        :return: nothing
        """
        instance_tags = instance_config.instance_tags

        state = self._collect_components(instance_config, timeout)

        for component in state['result']:
            comp_name = component['name'].encode('utf-8')
            external_id = str(comp_name) if isinstance(comp_name, bytes) else comp_name
            comp_type = component['sys_class_name']
            data = {
                "sys_id": component['sys_id'],
                "tags": instance_tags
            }

            self.component(external_id, comp_type, data)

    def _collect_relation_types(self, instance_config, timeout):
        """
        collects relations from CMDB
        :return: dict, raw response from CMDB
        """

        base_url = instance_config.base_url
        auth = instance_config.auth
        url = base_url + '/api/now/table/cmdb_rel_type?sysparm_fields=sys_id,parent_descriptor'

        return self._get_json(url, timeout, auth)

    def _process_and_cache_relation_types(self, instance_config, timeout):
        """
        collect available relations from cmdb_rel_ci and cache them in self.relation_types dict.
        :return: nothing
        """
        relation_types = {}
        state = self._collect_relation_types(instance_config, timeout)

        for relation in state['result']:
            id = relation['sys_id']
            parent_descriptor = relation['parent_descriptor']
            relation_types[id] = parent_descriptor
        return relation_types

    def _collect_component_relations(self, instance_config, timeout, offset, batch_size):
        """
        collect relations between components from cmdb_rel_ci and publish these in batches.
        """
        base_url = instance_config.base_url
        auth = instance_config.auth
        url = base_url + '/api/now/table/cmdb_rel_ci?sysparm_fields=parent,type,child'

        return self._get_json_batch(url, offset, batch_size, timeout, auth)

    def _process_component_relations(self, instance_config, batch_size, timeout, relation_types):
        offset = 0
        instance_tags = instance_config.instance_tags

        completed = False
        while not completed:
            state = self._collect_component_relations(instance_config, timeout, offset, batch_size)['result']

            for relation in state:

                parent_sys_id = relation['parent']['value']
                child_sys_id = relation['child']['value']
                type_sys_id = relation['type']['value']

                relation_type = relation_types[type_sys_id]
                data = {
                    "tags": instance_tags
                }

                self.relation(parent_sys_id, child_sys_id, relation_type, data)

            completed = len(state) < batch_size
            offset += batch_size

    def _get_json_batch(self, url, offset, batch_size, timeout, auth):
        limit_args = "&sysparm_query=ORDERBYsys_created_on&sysparm_offset=%i&sysparm_limit=%i" % (offset, batch_size)
        limited_url = url + limit_args
        return self._get_json(limited_url, timeout, auth)

    def _get_json(self, url, timeout, auth=None, verify=True):
        tags = ["url:%s" % url]
        msg = None
        status = None
        resp = None
        try:
            resp = requests.get(url, timeout=timeout, auth=auth, verify=verify)
            if resp.status_code != 200:
                status = AgentCheck.CRITICAL
                msg = "Got %s when hitting %s" % (resp.status_code, url)
        except requests.exceptions.Timeout:
            # If there's a timeout
            msg = "%s seconds timeout when hitting %s" % (timeout, url)
            status = AgentCheck.CRITICAL
        except Exception as e:
            msg = str(e)
            status = AgentCheck.CRITICAL
        finally:
            if status is AgentCheck.CRITICAL:
                self.service_check(self.SERVICE_CHECK_NAME, status, tags=tags,
                                   message=msg)
                raise Exception("Cannot connect to ServiceNow CMDB, please check your configuration.")

        if resp.encoding is None:
            resp.encoding = 'UTF8'
        resp = yaml.safe_load(resp.text)
        return resp
