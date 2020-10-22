# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import json

try:
    json_parse_exception = json.decoder.JSONDecodeError
except AttributeError:  # Python 2
    json_parse_exception = ValueError

# 3rd party
import requests

# project
from stackstate_checks.base import ConfigurationError, AgentCheck, TopologyInstance
from stackstate_checks.base.errors import CheckException

BATCH_DEFAULT_SIZE = 2500
BATCH_MAX_SIZE = 10000


class InstanceInfo:
    def __init__(self, instance_tags, base_url, auth, sys_class_filter, batch_size, timeout):
        self.instance_tags = instance_tags
        self.base_url = base_url
        self.auth = auth
        self.sys_class_filter = sys_class_filter
        self.batch_size = batch_size
        self.timeout = timeout


class ServicenowCheck(AgentCheck):
    INSTANCE_TYPE = "servicenow_cmdb"
    SERVICE_CHECK_NAME = "servicenow.cmdb.topology_information"

    def get_instance_key(self, instance):
        base_url, _, _ = self._get_mandatory_instance_values(instance)
        return TopologyInstance(self.INSTANCE_TYPE, base_url, with_snapshots=False)

    def check(self, instance):
        base_url, password, user = self._get_mandatory_instance_values(instance)
        auth = (user, password)
        batch_size = instance.get('batch_size', 2500)
        if batch_size > BATCH_MAX_SIZE:
            raise ConfigurationError('Setting batch_size is {}. Max value is {}.'.format(batch_size, BATCH_MAX_SIZE))
        instance_tags = instance.get('tags', [])
        sys_class_filter = instance.get('include_resource_types', [])

        default_timeout = self.init_config.get('default_timeout', 20)
        timeout = float(instance.get('timeout', default_timeout))

        instance_config = InstanceInfo(instance_tags, base_url, auth, sys_class_filter, batch_size, timeout)

        try:
            self.start_snapshot()
            self._collect_and_process(self._collect_components, self._process_components, instance_config)
            self._collect_and_process(self._collect_relations, self._process_relations, instance_config)
            self.stop_snapshot()
            # Report ServiceCheck OK
            msg = "ServiceNow CMDB instance detected at %s " % base_url
            tags = ["url:%s" % base_url]
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=tags, message=msg)
        except Exception as e:
            self.log.exception(e)
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

    @staticmethod
    def filter_empty_metadata(data):
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

    def _collect_components(self, instance_config, offset):
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
        return self._get_json_batch(url, offset, instance_config.batch_size, instance_config.timeout, auth)

    def _collect_and_process(self, collect_function, process_function, instance_config):
        """
        batch processing of components or relations fetched from CMDB
        :return: nothing
        """
        offset = 0
        batch_number = 0
        completed = False

        while not completed:
            elements = collect_function(instance_config, offset)
            if "result" in elements and isinstance(elements["result"], list):
                number_of_elements_in_current_batch = len(elements.get("result"))
                process_function(elements, instance_config)
            else:
                raise CheckException('Method {} has no result'.format(collect_function))
            completed = number_of_elements_in_current_batch < instance_config.batch_size
            batch_number += 1
            offset += instance_config.batch_size
            self.log.info(
                'Processed batch no. {} with {} items.'.format(batch_number, number_of_elements_in_current_batch)
            )

    def _process_components(self, components, instance_config):
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
            data.update({"identifiers": identifiers, "tags": instance_config.instance_tags})

            self.component(external_id, comp_type, data)

    def _collect_relation_types(self, instance_config):
        """
        collects relations from CMDB
        :return: dict, raw response from CMDB
        """

        base_url = instance_config.base_url
        auth = instance_config.auth
        url = base_url + '/api/now/table/cmdb_rel_type?sysparm_fields=sys_id,parent_descriptor'

        return self._get_json(url, instance_config.timeout, auth)

    def _process_relation_types(self, instance_config):
        """
        collect available relations from cmdb_rel_ci
        """
        relation_types = {}
        state = self._collect_relation_types(instance_config)

        if "result" in state:
            for relation in state.get('result', []):
                sys_id = relation['sys_id']
                parent_descriptor = relation['parent_descriptor']
                relation_types[sys_id] = parent_descriptor
        return relation_types

    def _collect_relations(self, instance_config, offset):
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

        return self._get_json_batch(url, offset, instance_config.batch_size, instance_config.timeout, auth)

    def _process_relations(self, relations, instance_config):
        """
        process relations
        """
        relation_types = self._process_relation_types(instance_config)
        for relation in relations.get('result'):
            parent_sys_id = relation['parent']['value']
            child_sys_id = relation['child']['value']
            type_sys_id = relation['type']['value']

            relation_type = relation_types[type_sys_id]
            data = self.filter_empty_metadata(relation)
            data.update({"tags": instance_config.instance_tags})

            self.relation(parent_sys_id, child_sys_id, relation_type, data)

    def _get_json_batch(self, url, offset, batch_size, timeout, auth):
        if "?" not in url:
            query_delimiter = "?"
        else:
            query_delimiter = "&"
        limit_args = "{}sysparm_query=ORDERBYsys_created_on&sysparm_offset={}&sysparm_limit={}".format(query_delimiter,
                                                                                                       offset,
                                                                                                       batch_size)
        limited_url = url + limit_args
        return self._get_json(limited_url, timeout, auth)

    @staticmethod
    def _get_json(url, timeout, auth=None, verify=True):
        execution_time_exceeded_error_message = 'Transaction cancelled: maximum execution time exceeded'

        response = requests.get(url, timeout=timeout, auth=auth, verify=verify)
        if response.status_code != 200:
            raise CheckException("Got %s when hitting %s" % (response.status_code, url))

        try:
            response_json = json.loads(response.text.encode('utf-8'))
        except json_parse_exception as e:
            # Fix for ServiceNow bug: Sometimes there is a response with status 200 and malformed json with
            # error message 'Transaction cancelled: maximum execution time exceeded'.
            # We send right error message because json_parse_exception is just side effect error.
            if execution_time_exceeded_error_message in response.text:
                raise CheckException(execution_time_exceeded_error_message)
            else:
                raise e

        if response_json.get("error"):
            raise CheckException(response_json["error"].get("message"))

        return response_json

    @staticmethod
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
