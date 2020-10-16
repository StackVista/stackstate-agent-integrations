# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# 3rd party
import requests

# project
from stackstate_checks.base import ConfigurationError, AgentCheck, TopologyInstance
from stackstate_checks.base.errors import CheckException

# inbuilt
import yaml

EVENT_TYPE = SOURCE_TYPE_NAME = 'servicenow'


def _get_mandatory_instance_values(instance):
    """
    Check if mandatory instance values are present
    :param instance:
    :return: Strings base_url, password, user
    """
    try:
        user = instance['user']
        password = instance['password']
        base_url = instance['url']
    except KeyError as e:
        raise ConfigurationError('ServiceNow CMDB topology instance missing "{}" value.'.format(e))
    return base_url, password, user


class InstanceInfo:
    def __init__(self, instance_tags, base_url, auth, sys_class_filter):
        self.instance_tags = instance_tags
        self.base_url = base_url
        self.auth = auth
        self.sys_class_filter = sys_class_filter


class ServicenowCheck(AgentCheck):
    INSTANCE_TYPE = "servicenow_cmdb"
    SERVICE_CHECK_NAME = "servicenow.cmdb.topology_information"

    def get_instance_key(self, instance):
        base_url, _, _ = _get_mandatory_instance_values(instance)
        return TopologyInstance(self.INSTANCE_TYPE, base_url, with_snapshots=False)

    def check(self, instance):
        base_url, password, user = _get_mandatory_instance_values(instance)
        auth = (user, password)
        batch_size = instance.get('batch_size', 10000)
        instance_tags = instance.get('tags', [])
        sys_class_filter = instance.get('include_resource_types', [])

        default_timeout = self.init_config.get('default_timeout', 20)
        timeout = float(instance.get('timeout', default_timeout))

        instance_config = InstanceInfo(instance_tags, base_url, auth, sys_class_filter)

        try:
            self.start_snapshot()
            relation_types = self._process_and_cache_relation_types(instance_config, timeout)
            self._process_components(instance_config, batch_size, timeout)
            self._process_component_relations(instance_config, batch_size, timeout, relation_types)
            # Report ServiceCheck OK
            msg = "ServiceNow CMDB instance detected at %s " % base_url
            tags = ["url:%s" % base_url]
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=tags, message=msg)
            self.stop_snapshot()
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e), tags=instance_tags)

    def get_sys_class_component_filter_query(self, sys_class_filter):
        """
        Return the sys_parm_query on the basis of sys_class_name filters from configuration
        :param sys_class_filter: a filter with list of sys_class_name
        :return: sysparm_query for url or ""
        """
        sysparm_query = ""
        if len(sys_class_filter) > 0:
            sysparm_query = "sysparm_query=sys_class_nameIN{}".format(sys_class_filter[0])
            for sys_class in sys_class_filter[1:]:
                sysparm_query = sysparm_query + "%2C{}".format(sys_class)
        self.log.debug("sys param query for component is :- " + sysparm_query)
        return sysparm_query

    def get_sys_class_relation_filter_query(self, sys_class_filter):
        sysparm_parent_query = ""
        sysparm_child_query = ""
        if len(sys_class_filter) > 0:
            sysparm_parent_query = "sysparm_query=parent.sys_class_nameIN{}".format(sys_class_filter[0])
            sysparm_child_query = "%5Echild.sys_class_nameIN{}".format(sys_class_filter[0])
            for sys_class in sys_class_filter[1:]:
                sysparm_parent_query = sysparm_parent_query + "%2C{}".format(sys_class)
                sysparm_child_query = sysparm_child_query + "%2C{}".format(sys_class)
        sysparm_query = sysparm_parent_query + sysparm_child_query
        self.log.debug("sys param query for relation is :- " + sysparm_query)
        return sysparm_query

    def filter_empty_metadata(self, data):
        """
        Filter the empty key:value in metadata and also convert unicode values to sting
        :param data: metadata from servicenow
        :return: filtered metadata
        """
        result = {}
        if isinstance(data, dict):
            for k, v in data.items():
                if v:
                    if str(type(v)) == "<type 'unicode'>":
                        # only possible in Python 2
                        v = v.encode('utf-8')
                    result[k] = v
        return result

    def _collect_components(self, instance_config, offset, batch_size, timeout):
        """
        collect components from ServiceNow CMDB's cmdb_ci table
        (API Doc- https://developer.servicenow.com/app.do#!/rest_api_doc?v=london&id=r_TableAPI-GET)

        :return: dict, raw response from CMDB
        """

        base_url = instance_config.base_url
        auth = instance_config.auth
        sys_class_filter = instance_config.sys_class_filter
        url = base_url + '/api/now/table/cmdb_ci'
        sys_class_filter_query = self.get_sys_class_component_filter_query(sys_class_filter)
        if sys_class_filter_query:
            url = url + "?{}".format(sys_class_filter_query)
            self.log.debug("URL for component collection after applying filter:- %s", url)
        return self._get_json_batch(url, offset, batch_size, timeout, auth)

    def _process_components(self, instance_config, batch_size, timeout):
        """
        process components fetched from CMDB
        :return: nothing
        """
        instance_tags = instance_config.instance_tags
        offset = 0

        completed = False
        while not completed:
            components = self._collect_components(instance_config, offset, batch_size, timeout)
            if "result" in components and isinstance(components["result"], list):
                number_of_components_in_current_batch = len(components.get("result"))
                for component in components.get('result'):
                    data = {}
                    component = self.filter_empty_metadata(component)
                    identifiers = []
                    comp_name = component.get('name')
                    comp_type = component.get('sys_class_name')
                    external_id = component.get('sys_id')

                    if 'fqdn' in component and component['fqdn']:
                        identifiers.append("urn:host:/{}".format(component['fqdn']))
                    if 'host_name' in component and component['host_name']:
                        identifiers.append("urn:host:/{}".format(component['host_name']))
                    else:
                        identifiers.append("urn:host:/{}".format(comp_name))
                    identifiers.append(external_id)
                    data.update(component)
                    data.update({"identifiers": identifiers, "tags": instance_tags})

                    self.component(external_id, comp_type, data)
            else:
                raise CheckException('Collect components has no result')
            completed = number_of_components_in_current_batch < batch_size
            offset += batch_size

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

        if "result" in state:
            for relation in state.get('result', []):
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
        sys_class_filter = instance_config.sys_class_filter
        url = base_url + '/api/now/table/cmdb_rel_ci'
        sys_class_filter_query = self.get_sys_class_relation_filter_query(sys_class_filter)
        if sys_class_filter_query:
            url = url + "?{}".format(sys_class_filter_query)
            self.log.debug("URL for relation collection after applying filter:- %s", url)

        return self._get_json_batch(url, offset, batch_size, timeout, auth)

    def _process_component_relations(self, instance_config, batch_size, timeout, relation_types):
        offset = 0
        instance_tags = instance_config.instance_tags

        completed = False
        while not completed:
            relations = self._collect_component_relations(instance_config, timeout, offset, batch_size)
            total_relations = len(relations.get("result"))
            if "result" in relations and isinstance(relations["result"], list):
                for relation in relations.get('result'):
                    parent_sys_id = relation['parent']['value']
                    child_sys_id = relation['child']['value']
                    type_sys_id = relation['type']['value']

                    relation_type = relation_types[type_sys_id]
                    data = self.filter_empty_metadata(relation)
                    data.update({"tags": instance_tags})

                    self.relation(parent_sys_id, child_sys_id, relation_type, data)
            completed = total_relations < batch_size
            offset += batch_size

    def _get_json_batch(self, url, offset, batch_size, timeout, auth):
        if "?" not in url:
            limit_args = "?"
        else:
            limit_args = "&"
        limit_args = "{}sysparm_query=ORDERBYsys_created_on&sysparm_offset={}&sysparm_limit={}".format(limit_args,
                                                                                                       offset,
                                                                                                       batch_size)
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
                raise CheckException("Cannot connect to ServiceNow CMDB, please check your configuration.")

        if resp.encoding is None:
            resp.encoding = 'UTF8'
        try:
            resp = yaml.safe_load(resp.text.encode("utf-8"))
        except Exception as e:
            self.log.exception(str(e))
            raise CheckException("Exception occurred while parsing response and the error is : {}".format(str(e)))

        if "error" in resp and resp["error"]:
            raise CheckException("Problem in collecting CIs : {}".format(resp["error"].get("message")))
        return resp
