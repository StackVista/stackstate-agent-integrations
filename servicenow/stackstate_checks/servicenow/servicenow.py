# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import json

from requests import Session

from stackstate_checks.servicenow import State, InstanceInfo
from stackstate_checks.servicenow.common import API_SNOW_TABLE_CMDB_CI, API_SNOW_TABLE_CMDB_REL_CI, \
    API_SNOW_TABLE_CHANGE_REQUEST
from stackstate_checks.servicenow.models import ChangeRequest, ConfigurationItem, CIRelation

try:
    json_parse_exception = json.decoder.JSONDecodeError
except AttributeError:  # Python 2
    json_parse_exception = ValueError

from schematics.exceptions import DataError

from stackstate_checks.base import AgentCheck, StackPackInstance, Identifiers, to_string
from stackstate_checks.base.errors import CheckException


class ServicenowCheck(AgentCheck):
    INSTANCE_TYPE = "servicenow_cmdb"
    SERVICE_CHECK_NAME = "servicenow.cmdb.topology_information"
    INSTANCE_SCHEMA = InstanceInfo

    def get_instance_key(self, instance_info):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance_info.url))

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
            self._process_planned_change_requests(instance_info)
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
    def select_metadata_field(data, display_value_list):
        """
        Retrieve the proper attribute either `display_value` or `value` from data
        :param data: metadata from servicenow
        :param display_value_list: list of attributes for which `display_value` to be extracted
        :return: metadata with applied field
        """
        result = {}
        if isinstance(data, dict):
            for k, v in data.items():
                # since display_param_value always returns dictionary for all keys
                if isinstance(v, dict):
                    if k in display_value_list:
                        if v.get("display_value"):
                            result[k] = to_string(v.get("display_value"))
                            continue
                    result[k] = to_string(v.get("value"))

        return result

    def _batch_collect_components(self, instance_info, offset):
        """
        collect components from ServiceNow CMDB's cmdb_ci table
        (API Doc- https://developer.servicenow.com/app.do#!/rest_api_doc?v=london&id=r_TableAPI-GET)

        :return: dict, raw response from CMDB
        """
        auth = (instance_info.user, instance_info.password)
        cert = (instance_info.cert, instance_info.keyfile)
        url = instance_info.url + API_SNOW_TABLE_CMDB_CI
        sys_class_filter_query = self._get_sys_class_component_filter_query(instance_info.include_resource_types)
        params = self._params_append_to_sysparm_query(add_to_query=sys_class_filter_query)
        params = self._params_append_to_sysparm_query(add_to_query=instance_info.cmdb_ci_sysparm_query, params=params)
        params = self._prepare_json_batch_params(params, offset, instance_info.batch_size)
        return self._get_json(url, instance_info.timeout, params, auth, instance_info.verify_https, cert)

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
        :return: None
        """
        collected_components = self._batch_collect(self._batch_collect_components, instance_info)

        for component in collected_components:
            try:
                config_item = ConfigurationItem(component, strict=False)
                config_item.validate()
            except DataError as e:
                self.log.warning("Error while processing properties of CI {} having sys_id {} - {}"
                                 .format(config_item.sys_id.value, config_item.name.value, e))
                continue
            data = {}
            component = self.select_metadata_field(component, instance_info.component_display_value_list)
            identifiers = []
            comp_name = config_item.name.value
            comp_type = config_item.sys_class_name.value
            external_id = config_item.sys_id.value

            if config_item.fqdn.value:
                identifiers.append(Identifiers.create_host_identifier(to_string(config_item.fqdn.value)))
            if config_item.host_name.value:
                identifiers.append(Identifiers.create_host_identifier(to_string(config_item.host_name.value)))
            else:
                identifiers.append(Identifiers.create_host_identifier(to_string(comp_name)))
            identifiers.append(external_id)
            identifiers = Identifiers.append_lowercase_identifiers(identifiers)
            data.update(component)
            tags = instance_info.instance_tags
            sys_tags = config_item.sys_tags.display_value
            if sys_tags:
                sys_tags = list(map(lambda x: x.strip(), sys_tags.split(",")))
                tags = tags + sys_tags
            data.update({"identifiers": identifiers, "tags": tags})

            self.component(external_id, comp_type, data)

    def _batch_collect_relations(self, instance_info, offset):
        """
        collect relations between components from cmdb_rel_ci and publish these in batches.
        """
        auth = (instance_info.user, instance_info.password)
        cert = (instance_info.cert, instance_info.keyfile)
        url = instance_info.url + API_SNOW_TABLE_CMDB_REL_CI
        sys_class_filter_query = self._get_sys_class_relation_filter_query(instance_info.include_resource_types)
        params = self._params_append_to_sysparm_query(add_to_query=sys_class_filter_query)
        params = self._params_append_to_sysparm_query(add_to_query=instance_info.cmdb_rel_ci_sysparm_query,
                                                      params=params)
        params = self._prepare_json_batch_params(params, offset, instance_info.batch_size)
        return self._get_json(url, instance_info.timeout, params, auth, instance_info.verify_https, cert)

    def _process_relations(self, instance_info):
        """
        process relations
        """
        collected_relations = self._batch_collect(self._batch_collect_relations, instance_info)
        for relation in collected_relations:
            try:
                ci_relation = CIRelation(relation, strict=False)
                ci_relation.validate()
            except DataError as e:
                self.log.warning("Error while processing properties of relation having Sys ID {} - {}"
                                 .format(ci_relation.sys_id.value, e))
                continue
            data = {}
            relation = self.select_metadata_field(relation, instance_info.relation_display_value_list)
            parent_sys_id = ci_relation.parent.value
            child_sys_id = ci_relation.child.value
            # first part after splitting with :: contains actual relation
            relation_type = ci_relation.type.display_value.split("::")[0]

            # relation_type = relation_types[type_sys_id]
            data.update(relation)
            tags = instance_info.instance_tags
            sys_tags = ci_relation.sys_tags.display_value
            if sys_tags:
                tags = tags + sys_tags.split(",")
            data.update({"tags": tags})

            self.relation(parent_sys_id, child_sys_id, relation_type, data)

    def _collect_change_requests_updates(self, instance_info):
        """
        Constructs params for getting new Change Requests (CR) and CRs updated after the last time we queried
        ServiceNow for them. Last query time is persisted in InstanceInfo.state.latest_sys_updated_on.
        :param instance_info: instance object
        :return: dict with servicenow rest api response
        """
        reformatted_date = instance_info.state.latest_sys_updated_on.strftime("'%Y-%m-%d', '%H:%M:%S'")
        sysparm_query = 'sys_updated_on>javascript:gs.dateGenerate(%s)' % reformatted_date
        self.log.debug('sysparm_query: %s', sysparm_query)
        return self._collect_change_requests(instance_info, sysparm_query)

    def _collect_planned_change_requests(self, instance_info):
        """
        Constructs params for getting planned Change Requests (CR) from ServiceNow.
        CR can be planned in advance, sometimes by as much as a few months. CRs in ServiceNow have a Planned Start Date
        field that tracks this. We select CRs with Planned Start Date set for today or tomorrow.
        :param instance_info: instance object
        :return: dict with servicenow rest api response
        """
        sysparm_query = 'start_dateONToday@javascript:gs.beginningOfToday()@javascript:gs.endOfToday()' \
                        '^ORstart_dateONTomorrow@javascript:gs.beginningOfTomorrow()@javascript:gs.endOfTomorrow()'
        self.log.debug('sysparm_query: %s', sysparm_query)
        return self._collect_change_requests(instance_info, sysparm_query)

    def _collect_change_requests(self, instance_info, sysparm_query):
        """
        Prepares ServiceNow call for change request rest api endpoint.
        :param instance_info: instance object
        :param sysparm_query: custom params for rest api call
        :return: dict with servicenow rest api response
        """
        params = {
            'sysparm_display_value': 'all',
            'sysparm_exclude_reference_link': 'true',
            'sysparm_limit': instance_info.change_request_process_limit,
            'sysparm_query': sysparm_query
        }
        params = self._params_append_to_sysparm_query(instance_info.change_request_sysparm_query, params)
        auth = (instance_info.user, instance_info.password)
        cert = (instance_info.cert, instance_info.keyfile)
        url = instance_info.url + API_SNOW_TABLE_CHANGE_REQUEST
        return self._get_json(url, instance_info.timeout, params, auth, instance_info.verify_https, cert)

    def _validate_and_filter_change_requests_response(self, response, instance_info):
        """
        CR validation with Schematics model. CR needs to have assigned CMDB_CI to connect it to STS topology component.
        :param response: ServiceNow rest api response as dict
        :param instance_info: instance object
        :return: ChangeRequest list
        """
        change_requests = []
        for cr in response.get('result', []):
            try:
                mapping = {
                    'custom_cmdb_ci': instance_info.custom_cmdb_ci_field,
                    'custom_planned_start_date': instance_info.custom_planned_start_date_field,
                    'custom_planned_end_date': instance_info.custom_planned_end_date_field,
                }
                change_request = ChangeRequest(cr, strict=False, deserialize_mapping=mapping)
                change_request.validate()
            except DataError as e:
                self.log.warning('%s - DataError: %s. This CR is skipped.', cr['number']['value'], e)
                continue
            # Change request must have CMDB_CI to be connected to STS component
            if change_request.custom_cmdb_ci.value:
                change_requests.append(change_request)
                self.log.debug(
                    'CR %s: CMDB_CI: %s - sys_updated_on value: %s display_value: %s',
                    change_request.number.display_value,
                    change_request.custom_cmdb_ci.display_value,
                    change_request.sys_updated_on.value,
                    change_request.sys_updated_on.display_value
                )
        return change_requests

    def _process_change_requests(self, instance_info):
        """
        Change Requests (CR) need to fit the following criteria to be send to StackState as Topology Event:
        - new CR that is created after last time we queried ServiceNow
        - existing CR that is updated after last time we queried ServiceNow and their State has changed
        :param instance_info: Instance object
        :return: None
        """
        number_of_new_crs = 0
        self.log.debug('Begin processing change requests.')
        response_new_crs = self._collect_change_requests_updates(instance_info)
        for change_request in self._validate_and_filter_change_requests_response(response_new_crs, instance_info):
            if change_request.sys_updated_on.value > instance_info.state.latest_sys_updated_on:
                instance_info.state.latest_sys_updated_on = change_request.sys_updated_on.value
                self.log.debug('New sys_updated_on %s writen.', change_request.sys_updated_on.value)
            cr = change_request.number.display_value
            new_cr_state = change_request.state.display_value
            old_cr_state = instance_info.state.change_requests.get(cr)
            if old_cr_state is None or old_cr_state != new_cr_state:
                self._create_event_from_change_request(change_request)
                instance_info.state.change_requests[cr] = new_cr_state
                self.log.debug('CR %s new state %s.', cr, new_cr_state)
                number_of_new_crs += 1
        if number_of_new_crs:
            self.log.info('Created %d new Change Requests events.', number_of_new_crs)

    def _process_planned_change_requests(self, instance_info):
        """
        Planned Change Requests (CR) were created in the past, and they are due today so we resend them 1 hour before
        their Planned Start Date. 1 hour is default value. It can be changed in check config.
        InstanceInfo.state.planned_change_requests_cache holds list of sent Planned CRs so we don't resend them.
        :param instance_info: Instance object
        :return: None
        """
        number_of_planned_crs = 0
        self.log.debug('Begin processing planned change requests.')
        response_planned_crs = self._collect_planned_change_requests(instance_info)
        for change_request in self._validate_and_filter_change_requests_response(response_planned_crs, instance_info):
            if change_request.custom_planned_start_date:
                cr = change_request.number.display_value
                start = datetime.datetime.strptime(
                    change_request.custom_planned_start_date.display_value, '%Y-%m-%d %H:%M:%S'
                )
                resend = start - datetime.timedelta(hours=instance_info.planned_change_request_resend_schedule)
                now = datetime.datetime.now()
                self.log.debug('CR %s Planned start: %s Resend schedule: %s Now: %s', cr, start, resend, now)
                if resend <= now < start:
                    if cr not in instance_info.state.sent_planned_crs_cache:
                        self._create_event_from_change_request(change_request)
                        instance_info.state.sent_planned_crs_cache.append(cr)
                        self.log.debug('Added CR %s to sent_planned_crs_cache.', cr)
                        number_of_planned_crs += 1
                    else:
                        self.log.debug('CR %s is in sent_planned_crs_cache.', cr)
                elif start < now and cr in instance_info.state.sent_planned_crs_cache:
                    instance_info.state.sent_planned_crs_cache.remove(cr)
                    self.log.debug('Removed CR %s from sent_planned_crs_cache.', cr)
        if number_of_planned_crs:
            self.log.info('Sent %d planned Change Requests.', number_of_planned_crs)

    def _create_event_from_change_request(self, change_request):
        """
        StackState topology event is created from ServiceNow Change Request (CR).
        Time of event is based on when the CR was last time updated.
        :param change_request: ChangeRequest object
        :return: None
        """
        host = Identifiers.create_host_identifier(to_string(change_request.custom_cmdb_ci.display_value))
        identifiers = [change_request.custom_cmdb_ci.value, host]
        identifiers = Identifiers.append_lowercase_identifiers(identifiers)
        timestamp = (change_request.sys_updated_on.value - datetime.datetime.utcfromtimestamp(0)).total_seconds()
        msg_title = '%s: %s' % (change_request.number.display_value,
                                change_request.short_description.display_value or 'No short description')
        msg_txt = change_request.description.display_value or 'No description'
        tags = [
            'number:%s' % change_request.number.display_value,
            'priority:%s' % change_request.priority.display_value,
            'risk:%s' % change_request.risk.display_value,
            'impact:%s' % change_request.impact.display_value,
            'state:%s' % change_request.state.display_value,
            'category:%s' % change_request.category.display_value,
        ]
        event_type = 'Change Request %s' % change_request.type.display_value

        self.log.debug('Creating STS topology event from SNOW CR %s', change_request.number.display_value)

        self.event({
            'timestamp': timestamp,
            'event_type': event_type,
            'msg_title': msg_title,
            'msg_text': msg_txt,
            'context': {
                'source': 'servicenow',
                'category': 'change_request',
                'element_identifiers': identifiers,
                'source_links': [],
                'data': {
                    'requested_by': change_request.requested_by.display_value,
                    'assignment_group': change_request.assignment_group.display_value,
                    'assigned_to': change_request.assigned_to.display_value,
                    'conflict_status': change_request.conflict_status.display_value,
                    'conflict_last_run': change_request.conflict_last_run.display_value,
                    'service_offering': change_request.service_offering.display_value,
                    'start_date': change_request.custom_planned_start_date.display_value,
                    'end_date': change_request.custom_planned_end_date.display_value,
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
                'sysparm_display_value': 'all',
                'sysparm_offset': offset,
                'sysparm_limit': batch_size
            }
        )
        return params

    def _get_json(self, url, timeout, params, auth=None, verify=True, cert=None):
        execution_time_exceeded_error_message = 'Transaction cancelled: maximum execution time exceeded'

        with Session() as session:
            session.verify = verify
            if cert:
                session.cert = cert
            response = session.get(url, params=params, auth=auth, timeout=timeout)

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
                raise CheckException('ServiceNow error: "%s" in response from url %s' %
                                     (response_json['error'].get('message'), response.url))

            if response_json.get('result'):
                self.log.debug('Got %d results in response', len(response_json['result']))

        return response_json
