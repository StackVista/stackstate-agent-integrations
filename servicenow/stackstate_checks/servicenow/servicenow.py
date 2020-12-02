# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import json

from stackstate_checks.base.utils.schemas import StrictStringType

try:
    json_parse_exception = json.decoder.JSONDecodeError
except AttributeError:  # Python 2
    json_parse_exception = ValueError

import requests
from schematics import Model
from schematics.exceptions import DataError
from schematics.types import URLType, StringType, ListType, IntType, DictType, DateTimeType, ModelType, BaseType, \
    BooleanType

from stackstate_checks.base import AgentCheck, TopologyInstance, Identifiers, to_string
from stackstate_checks.base.errors import CheckException

BATCH_DEFAULT_SIZE = 2500
BATCH_MAX_SIZE = 10000
TIMEOUT = 20
VERIFY_HTTPS = True
CRS_BOOTSTRAP_DAYS_DEFAULT = 100
CRS_DEFAULT_PROCESS_LIMIT = 1000


class WrapperType(BaseType):
    def __init__(self, field, value_mapping, **kwargs):
        self.field = field(**kwargs)
        self.value_mapping = value_mapping
        super(WrapperType, self).__init__(**kwargs)

    def convert(self, value, context=None):
        if context.new:
            value = self.value_mapping(value)
        if value is None:
            if self.default is not None:
                return self.default
            else:
                return value
        return self.field.convert(value, context)

    def export(self, value, format, context=None):
        self.field.export(value, format, context)


class ChangeRequest(Model):
    number = WrapperType(StringType, required=True, value_mapping=lambda x: x['display_value'])
    state = WrapperType(StringType, required=True, value_mapping=lambda x: x['display_value'])
    cmdb_ci = DictType(StrictStringType(accept_empty=False), required=True)
    sys_updated_on = WrapperType(DateTimeType, required=True, value_mapping=lambda x: x['value'])
    business_service = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    service_offering = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    short_description = WrapperType(StringType, required=True, value_mapping=lambda x: x['display_value'])
    description = WrapperType(StringType, default='No description', value_mapping=lambda x: x['display_value'])
    type = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    priority = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    impact = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    risk = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    requested_by = WrapperType(StringType, value_mapping=lambda x: x['display_value'])
    category = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    conflict_status = WrapperType(StringType, value_mapping=lambda x: x['value'], default='')
    conflict_last_run = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    assignment_group = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')
    assigned_to = WrapperType(StringType, value_mapping=lambda x: x['display_value'], default='')


class State(Model):
    latest_sys_updated_on = DateTimeType(required=True)
    change_requests = DictType(StringType, default={})


class InstanceInfo(Model):
    url = URLType(required=True)
    user = StringType(required=True)
    password = StringType(required=True)
    include_resource_types = ListType(StringType, default=[])
    batch_size = IntType(default=BATCH_DEFAULT_SIZE, max_value=BATCH_MAX_SIZE)
    timeout = IntType(default=TIMEOUT)
    verify_https = BooleanType(default=VERIFY_HTTPS)
    instance_tags = ListType(StringType, default=[])
    change_request_bootstrap_days = IntType(default=CRS_BOOTSTRAP_DAYS_DEFAULT)
    change_request_process_limit = IntType(default=CRS_DEFAULT_PROCESS_LIMIT)
    cmdb_ci_sysparm_query = StringType()
    cmdb_rel_ci_sysparm_query = StringType()
    change_request_sysparm_query = StringType()
    state = ModelType(State)


class ServicenowCheck(AgentCheck):
    INSTANCE_TYPE = "servicenow_cmdb"
    SERVICE_CHECK_NAME = "servicenow.cmdb.topology_information"
    INSTANCE_SCHEMA = InstanceInfo

    def get_instance_key(self, instance):
        instance_info = InstanceInfo(instance)
        instance_info.validate()
        return TopologyInstance(self.INSTANCE_TYPE, str(instance_info.url), with_snapshots=False)

    def check(self, instance_info):
        try:
            if not instance_info.state:
                # Create empty state
                instance_info.state = State(
                    {
                        'latest_sys_updated_on': datetime.datetime.now() - datetime.timedelta(
                            days=instance_info.change_request_bootstrap_days
                        )
                    }
                )

            self.start_snapshot()
            self._process_components(instance_info)
            self._process_relations(instance_info)
            self._process_change_requests(instance_info)
            self.stop_snapshot()
            msg = "ServiceNow CMDB instance detected at %s " % instance_info.url
            tags = ["url:%s" % instance_info.url]
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=tags, message=msg)
        except Exception as e:
            self.log.exception(e)
            msg = '%s: %s' % (type(e).__name__, str(e))
            self.service_check(
                self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=msg, tags=instance_info.instance_tags
            )

    def _get_sys_class_component_filter_query(self, sys_class_filter):
        """
        Return the sys_parm_query on the basis of sys_class_name filters from configuration
        :param sys_class_filter: a filter with list of sys_class_name
        :return: sysparm_query for url or ""
        """
        sysparm_query = ""
        if len(sys_class_filter) > 0:
            sysparm_query = "sys_class_nameIN%s" % sys_class_filter[0]
            if len(sys_class_filter[1:]) > 0:
                sysparm_query = "%s,%s" % (sysparm_query, ",".join(sys_class_filter[1:]))
        if sysparm_query:
            self.log.debug('sysparm_query for component: %s', sysparm_query)
        return sysparm_query

    def _get_sys_class_relation_filter_query(self, sys_class_filter):
        sysparm_parent_query = ""
        sysparm_child_query = ""
        if len(sys_class_filter) > 0:
            sysparm_parent_query = "parent.sys_class_nameIN%s" % sys_class_filter[0]
            sysparm_child_query = "^child.sys_class_nameIN%s" % sys_class_filter[0]
            if len(sys_class_filter[1:]) > 0:
                sysparm_parent_query = "%s,%s" % (sysparm_parent_query, ",".join(sys_class_filter[1:]))
                sysparm_child_query = "%s,%s" % (sysparm_child_query, ",".join(sys_class_filter[1:]))
        sysparm_query = sysparm_parent_query + sysparm_child_query
        if sysparm_query:
            self.log.debug('sysparm_query for relation: %s', sysparm_query)
        return sysparm_query

    @staticmethod
    def _filter_empty_metadata(data):
        """
        Filter the empty key:value in metadata dictionary and fix utf-8 encoding problems
        :param data: metadata from servicenow
        :return: filtered metadata
        """
        result = {}
        if isinstance(data, dict):
            for k, v in data.items():
                if v:
                    result[k] = to_string(v)
        return result

    def _batch_collect_components(self, instance_info, offset):
        """
        collect components from ServiceNow CMDB's cmdb_ci table
        (API Doc- https://developer.servicenow.com/app.do#!/rest_api_doc?v=london&id=r_TableAPI-GET)

        :return: dict, raw response from CMDB
        """
        auth = (instance_info.user, instance_info.password)
        url = instance_info.url + '/api/now/table/cmdb_ci'
        sys_class_filter_query = self._get_sys_class_component_filter_query(instance_info.include_resource_types)
        params = self._params_append_to_sysparm_query(add_to_query=sys_class_filter_query)
        params = self._params_append_to_sysparm_query(add_to_query=instance_info.cmdb_ci_sysparm_query, params=params)
        params = self._prepare_json_batch_params(params, offset, instance_info.batch_size)
        return self._get_json(url, instance_info.timeout, params, auth, instance_info.verify_https)

    def _batch_collect(self, collect_function, instance_info):
        """
        batch processing of components or relations fetched from CMDB
        :return: collected components
        """
        offset = 0
        batch_number = 0
        completed = False
        collection = []

        while not completed:
            elements = collect_function(instance_info, offset)
            if "result" in elements and isinstance(elements["result"], list):
                number_of_elements_in_current_batch = len(elements.get("result"))
            else:
                raise CheckException('Method %s has no result' % collect_function)
            completed = number_of_elements_in_current_batch < instance_info.batch_size
            collection.extend(elements['result'])
            batch_number += 1
            offset += instance_info.batch_size
            self.log.info(
                '%s processed batch no. %d with %d items.',
                collect_function.__name__, batch_number, number_of_elements_in_current_batch
            )

        return collection

    def _process_components(self, instance_info):
        """
        Gets SNOW components name, external_id and other identifiers
        :param instance_info:
        :return:
        """
        collected_components = self._batch_collect(self._batch_collect_components, instance_info)

        for component in collected_components:
            data = {}
            component = self._filter_empty_metadata(component)
            identifiers = []
            comp_name = component.get('name')
            comp_type = component.get('sys_class_name')
            external_id = component.get('sys_id')

            if component.get('fqdn'):
                identifiers.append(Identifiers.create_host_identifier(to_string(component['fqdn'])))
            if component.get('host_name'):
                identifiers.append(Identifiers.create_host_identifier(to_string(component['host_name'])))
            else:
                identifiers.append(Identifiers.create_host_identifier(to_string(comp_name)))
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
        url = instance_info.url + '/api/now/table/cmdb_rel_type'
        params = {
            'sysparm_fields': 'sys_id,parent_descriptor'
        }
        return self._get_json(url, instance_info.timeout, params, auth, instance_info.verify_https)

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

    def _batch_collect_relations(self, instance_info, offset):
        """
        collect relations between components from cmdb_rel_ci and publish these in batches.
        """
        auth = (instance_info.user, instance_info.password)
        url = instance_info.url + '/api/now/table/cmdb_rel_ci'
        sys_class_filter_query = self._get_sys_class_relation_filter_query(instance_info.include_resource_types)
        params = self._params_append_to_sysparm_query(add_to_query=sys_class_filter_query)
        params = self._params_append_to_sysparm_query(add_to_query=instance_info.cmdb_rel_ci_sysparm_query,
                                                      params=params)
        params = self._prepare_json_batch_params(params, offset, instance_info.batch_size)
        return self._get_json(url, instance_info.timeout, params, auth, instance_info.verify_https)

    def _process_relations(self, instance_info):
        """
        process relations
        """
        relation_types = self._process_relation_types(instance_info)
        collected_relations = self._batch_collect(self._batch_collect_relations, instance_info)
        for relation in collected_relations:
            parent_sys_id = relation['parent']['value']
            child_sys_id = relation['child']['value']
            type_sys_id = relation['type']['value']

            relation_type = relation_types[type_sys_id]
            data = self._filter_empty_metadata(relation)
            data.update({"tags": instance_info.instance_tags})

            self.relation(parent_sys_id, child_sys_id, relation_type, data)

    def _collect_change_requests(self, instance_info):
        auth = (instance_info.user, instance_info.password)
        url = instance_info.url + '/api/now/table/change_request'
        reformatted_date = instance_info.state.latest_sys_updated_on.strftime("'%Y-%m-%d', '%H:%M:%S'")
        sysparm_query = 'sys_updated_on>javascript:gs.dateGenerate(%s)' % reformatted_date
        self.log.debug('sysparm_query: %s', sysparm_query)
        params = {
            'sysparm_display_value': 'all',
            'sysparm_exclude_reference_link': 'true',
            'sysparm_limit': instance_info.change_request_process_limit,
            'sysparm_query': sysparm_query
        }
        params = self._params_append_to_sysparm_query(instance_info.change_request_sysparm_query, params)
        return self._get_json(url, instance_info.timeout, params, auth, instance_info.verify_https)

    def _process_change_requests(self, instance_info):
        response = self._collect_change_requests(instance_info)
        self.log.debug('Received %d Change Requests', len(response['result']))
        for cr in response['result']:
            try:
                change_request = ChangeRequest(cr, strict=False)
                change_request.validate()
            except DataError as e:
                self.log.warning('%s - DataError: %s. This CR is skipped.', cr['number']['value'], e)
                continue
            if change_request.cmdb_ci:
                self.log.debug(
                    '%s: %s %s - sys_updated_on value: %s display_value: %s',
                    change_request.number,
                    change_request.cmdb_ci['value'],
                    change_request.cmdb_ci['display_value'],
                    cr['sys_updated_on']['value'],
                    cr['sys_updated_on']['display_value']
                )
                if change_request.sys_updated_on > instance_info.state.latest_sys_updated_on:
                    instance_info.state.latest_sys_updated_on = change_request.sys_updated_on
                old_state = instance_info.state.change_requests.get(change_request.number)
                if old_state is None or old_state != change_request.state:
                    self._create_event_from_change_request(change_request)
                    instance_info.state.change_requests[change_request.number] = change_request.state

    def _create_event_from_change_request(self, change_request):
        host = Identifiers.create_host_identifier(to_string(change_request.cmdb_ci['display_value']))
        identifiers = [change_request.cmdb_ci['value'], host]
        timestamp = (change_request.sys_updated_on - datetime.datetime.utcfromtimestamp(0)).total_seconds()
        msg_title = '%s: %s' % (change_request.number, change_request.short_description)
        tags = [
            'number:%s' % change_request.number,
            'priority:%s' % change_request.priority,
            'risk:%s' % change_request.risk,
            'state:%s' % change_request.state,
            'category:%s' % change_request.category,
            'conflict_status:%s' % change_request.conflict_status,
            'assigned_to:%s' % change_request.assigned_to
        ]
        event_type = 'Change Request %s' % change_request.type

        self.log.debug('Creating event from CR: %s', change_request.number)

        self.event({
            'timestamp': timestamp,
            'event_type': event_type,
            'msg_title': msg_title,
            'msg_text': change_request.description,
            'context': {
                'source': 'servicenow',
                'category': 'change_request',
                'element_identifiers': identifiers,
                'source_links': [],
                'data': {
                    'impact': change_request.impact,
                    'requested_by': change_request.requested_by,
                    'conflict_last_run': change_request.conflict_last_run,
                    'assignment_group': change_request.assignment_group,
                    'service_offering': change_request.service_offering,
                },
            },
            'tags': tags
        })

    def _params_append_to_sysparm_query(self, add_to_query, params=None):
        if params is None:
            params = {}
            self.log.debug('Creating new params dict.')
        if add_to_query:
            sysparm_query = params.pop('sysparm_query', '')
            if sysparm_query:
                sysparm_query += '^%s' % add_to_query
            else:
                sysparm_query = add_to_query
            params.update({'sysparm_query': sysparm_query})
        return params

    def _prepare_json_batch_params(self, params, offset, batch_size):
        params = self._params_append_to_sysparm_query("ORDERBYsys_created_on", params)
        params.update(
            {
                'sysparm_offset': offset,
                'sysparm_limit': batch_size
            }
        )
        return params

    def _get_json(self, url, timeout, params, auth=None, verify=True):
        execution_time_exceeded_error_message = 'Transaction cancelled: maximum execution time exceeded'

        response = requests.get(url, timeout=timeout, params=params, auth=auth, verify=verify)
        if response.status_code != 200:
            raise CheckException('Got status: %d when hitting %s' % (response.status_code, response.url))

        try:
            response_json = json.loads(response.text.encode('utf-8'))
        except UnicodeEncodeError as e:
            raise CheckException('Encoding error: "%s" in response from url %s' % (e, response.url))
        except json_parse_exception as e:
            # Fix for ServiceNow bug: Sometimes there is a response with status 200 and malformed json with
            # error message 'Transaction cancelled: maximum execution time exceeded'.
            # We send right error message because ParserError is just side effect error.
            if execution_time_exceeded_error_message in response.text:
                error_msg = 'ServiceNow Error "%s" in response from url %s' % (
                    execution_time_exceeded_error_message, response.url
                )
            else:
                error_msg = 'Json parse error: "%s" in response from url %s' % (e, response.url)
            raise CheckException(error_msg)

        if response_json.get('error'):
            raise CheckException(
                'ServiceNow error: "%s" in response from url %s' % (response_json['error'].get('message'), response.url)
            )

        if response_json.get('result'):
            self.log.debug('Got %d results in response', len(response_json['result']))

        return response_json
