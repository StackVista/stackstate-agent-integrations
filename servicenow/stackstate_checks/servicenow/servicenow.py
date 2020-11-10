# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime

import requests
import yaml
from schematics import Model
from schematics.types import URLType, StringType, ListType, IntType, BaseType
from yaml.parser import ParserError

from stackstate_checks.base import AgentCheck, TopologyInstance, Identifiers
from stackstate_checks.base.errors import CheckException

BATCH_DEFAULT_SIZE = 2500
BATCH_MAX_SIZE = 10000
TIMEOUT = 20

CR_STATE = {
    '-5': 'New',
    '-4': 'Assess',
    '-3': 'Authorize',
    '-2': 'Scheduled',
    '-1': 'Implement',
    '0': 'Review',
    '3': 'Closed',
    '4': 'Canceled'
}

CR_PRIORITY = {
    '1': 'Critical',
    '2': 'High',
    '3': 'Moderate',
    '4': 'Low'
}

CR_RISK = {
    '1': 'Very High',
    '2': 'High',
    '3': 'Moderate',
    '4': 'Low'
}

CR_IMPACT = {
    '1': 'High',
    '2': 'Medium',
    '3': 'Low'
}


class InstanceInfo(Model):
    url = URLType(required=True)
    user = StringType(required=True)
    password = StringType(required=True)
    include_resource_types = ListType(StringType, default=[])
    batch_size = IntType(default=BATCH_DEFAULT_SIZE, max_value=BATCH_MAX_SIZE)
    timeout = IntType(default=TIMEOUT)
    instance_tags = ListType(StringType, default=[])


class LinkType(BaseType):
    link = URLType()
    value = StringType()


class ChangeRequest(Model):
    number = StringType(required=True)
    cmdb_ci = LinkType(required=True)
    state = StringType(required=True)
    business_service = StringType()
    service_offering = StringType()
    short_description = StringType()
    description = StringType()
    type = StringType()
    priority = StringType(required=True)
    impact = StringType(required=True)
    risk = StringType(required=True)
    requested_by = LinkType()
    category = StringType()
    conflict_status = StringType()
    conflict_last_run = StringType()
    assignment_group = LinkType()
    assigned_to = LinkType()


class ServicenowCheck(AgentCheck):
    INSTANCE_TYPE = "servicenow_cmdb"
    SERVICE_CHECK_NAME = "servicenow.cmdb.topology_information"

    def get_instance_key(self, instance):
        instance_info = InstanceInfo(instance)
        instance_info.validate()
        return TopologyInstance(self.INSTANCE_TYPE, str(instance_info.url), with_snapshots=False)

    def check(self, instance):
        instance_info = InstanceInfo(instance)
        instance_info.validate()

        try:
            self.start_snapshot()
            self._collect_and_process(self._collect_components, self._process_components, instance_info)
            self._collect_and_process(self._collect_relations, self._process_relations, instance_info)
            self.stop_snapshot()
            msg = "ServiceNow CMDB instance detected at %s " % instance_info.url
            tags = ["url:%s" % instance_info.url]
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=tags, message=msg)
        except Exception as e:
            self.log.exception(e)
            msg = '{}: {}'.format(type(e).__name__, str(e))
            self.service_check(
                self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=msg, tags=instance_info.instance_tags
            )

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

    def _collect_components(self, instance_info, offset):
        """
        collect components from ServiceNow CMDB's cmdb_ci table
        (API Doc- https://developer.servicenow.com/app.do#!/rest_api_doc?v=london&id=r_TableAPI-GET)

        :return: dict, raw response from CMDB
        """

        auth = (instance_info.user, instance_info.password)
        url = instance_info.url + '/api/now/table/cmdb_ci'
        sys_class_filter_query = self.get_sys_class_component_filter_query(instance_info.include_resource_types)
        if sys_class_filter_query:
            url = url + "?{}".format(sys_class_filter_query)
            self.log.debug("URL for component collection after applying filter:- %s", url)
        return self._get_json_batch(url, offset, instance_info.batch_size, instance_info.timeout, auth)

    def _collect_and_process(self, collect_function, process_function, instance_info):
        """
        batch processing of components or relations fetched from CMDB
        :return: nothing
        """
        offset = 0
        batch_number = 0
        completed = False

        while not completed:
            elements = collect_function(instance_info, offset)
            if "result" in elements and isinstance(elements["result"], list):
                number_of_elements_in_current_batch = len(elements.get("result"))
                process_function(elements, instance_info)
            else:
                raise CheckException('Method {} has no result'.format(collect_function))
            completed = number_of_elements_in_current_batch < instance_info.batch_size
            batch_number += 1
            offset += instance_info.batch_size
            self.log.info(
                'Processed batch no. {} with {} items.'.format(batch_number, number_of_elements_in_current_batch)
            )

    def _process_components(self, components, instance_info):
        """
        Gets SNOW components name, external_id and other identifiers
        :param components:
        :param instance_info:
        :return:
        """
        for component in components.get('result'):
            data = {}
            component = self.filter_empty_metadata(component)
            identifiers = []
            comp_name = component.get('name')
            comp_type = component.get('sys_class_name')
            external_id = component.get('sys_id')

            if component.get('fqdn'):
                identifiers.append(Identifiers.create_host_identifier(component['fqdn']))
            if component.get('host_name'):
                identifiers.append(Identifiers.create_host_identifier(component['host_name']))
            else:
                identifiers.append(Identifiers.create_host_identifier(comp_name))
            identifiers.append(external_id)
            data.update(component)
            data.update({"identifiers": identifiers, "tags": instance_info.instance_tags})

            self.component(external_id, comp_type, data)

    def _collect_relation_types(self, instance_info):
        """
        collects relations from CMDB
        :return: dict, raw response from CMDB
        """
        auth = (instance_info.user, instance_info.password)
        url = instance_info.url + '/api/now/table/cmdb_rel_type?sysparm_fields=sys_id,parent_descriptor'
        return self._get_json(url, instance_info.timeout, auth)

    def _process_relation_types(self, instance_info):
        """
        collect available relations from cmdb_rel_ci
        """
        relation_types = {}
        types = self._collect_relation_types(instance_info)

        if "result" in types:
            for relation in types.get('result', []):
                sys_id = relation['sys_id']
                parent_descriptor = relation['parent_descriptor']
                relation_types[sys_id] = parent_descriptor
        return relation_types

    def _collect_relations(self, instance_info, offset):
        """
        collect relations between components from cmdb_rel_ci and publish these in batches.
        """
        auth = (instance_info.user, instance_info.password)
        url = instance_info.url + '/api/now/table/cmdb_rel_ci'
        sys_class_filter_query = self.get_sys_class_relation_filter_query(instance_info.include_resource_types)
        if sys_class_filter_query:
            url = url + "?{}".format(sys_class_filter_query)
            self.log.debug("URL for relation collection after applying filter:- %s", url)

        return self._get_json_batch(url, offset, instance_info.batch_size, instance_info.timeout, auth)

    def _process_relations(self, relations, instance_info):
        """
        process relations
        """
        relation_types = self._process_relation_types(instance_info)
        for relation in relations.get('result'):
            parent_sys_id = relation['parent']['value']
            child_sys_id = relation['child']['value']
            type_sys_id = relation['type']['value']

            relation_type = relation_types[type_sys_id]
            data = self.filter_empty_metadata(relation)
            data.update({"tags": instance_info.instance_tags})

            self.relation(parent_sys_id, child_sys_id, relation_type, data)

    def _collect_change_requests(self, instance_info):
        auth = (instance_info.user, instance_info.password)
        url = instance_info.url + '/api/now/table/change_request'
        return self._get_json(url, instance_info.timeout, auth)

    def _process_change_requests(self, instance_info):
        change_requests = self._collect_change_requests(instance_info)
        for cr in change_requests:
            change_request = ChangeRequest(cr, strict=False)
            change_request.validate()
            external_id = change_request.cmdb_ci.value
            tags = [
                'priority:{}'.format(change_request.priority),
                'risk:{}'.format(change_request.risk),
                'state:{}'.format(change_request.state),
                'category:{}'.format(change_request.category),
                'conflict_status:{}'.format(change_request.conflict_status),
                'assigned_to:{}'.format(change_request.assigned_to)
            ]
            identifiers = [external_id, Identifiers.create_host_identifier(change_request.name)]

            self.event({
                'timestamp': datetime.datetime.timestamp(change_request.sys_updated_on),
                'event_type': change_request.type,
                'msg_title': change_request.short_description,
                'msg_text': change_request.description,
                'aggregation_key': 'TODO',
                'context': {
                    'data': {
                        'cmdb_ci': identifiers,
                        'impact': change_request.impact,
                        'requested_by': change_request.requested_by,
                        'conflict_last_run': change_request.conflict_last_run,
                        'assignment_group': change_request.assignment_group
                    },
                },
                'tags': tags
            })

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
            response_json = yaml.safe_load(response.text.encode('utf-8'))
        except ParserError as e:
            # Fix for ServiceNow bug: Sometimes there is a response with status 200 and malformed json with
            # error message 'Transaction cancelled: maximum execution time exceeded'.
            # We send right error message because ParserError is just side effect error.
            if execution_time_exceeded_error_message in response.text:
                raise CheckException(execution_time_exceeded_error_message)
            else:
                raise e

        if response_json.get("error"):
            raise CheckException(response_json["error"].get("message"))

        return response_json
