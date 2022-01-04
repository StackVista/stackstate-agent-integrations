import json
import logging

try:
    json_parse_exception = json.decoder.JSONDecodeError
except AttributeError:  # Python 2
    json_parse_exception = ValueError

from requests import Session

from stackstate_checks.base.errors import CheckException

from stackstate_checks.servicenow.common import API_SNOW_TABLE_CMDB_CI, API_SNOW_TABLE_CMDB_REL_CI, \
    API_SNOW_TABLE_CHANGE_REQUEST


class ServiceNowClient:

    def __init__(self, instance_info):
        self.url = instance_info.url
        self.user = instance_info.user
        self.password = instance_info.password
        self.cert = instance_info.cert
        self.keyfile = instance_info.keyfile
        self.include_resource_types = instance_info.include_resource_types
        self.cmdb_ci_sysparm_query = instance_info.cmdb_ci_sysparm_query
        self.cmdb_rel_ci_sysparm_query = instance_info.cmdb_rel_ci_sysparm_query
        self.batch_size = instance_info.batch_size
        self.timeout = instance_info.timeout
        self.verify_https = instance_info.verify_https
        self.change_request_process_limit = instance_info.change_request_process_limit
        self.change_request_sysparm_query = instance_info.change_request_sysparm_query
        self.log = logging.getLogger(__name__)

    def collect_components(self):
        return self._batch_collect(self._batch_collect_components)

    def collect_relations(self):
        return self._batch_collect(self._batch_collect_relations)

    def collect_change_requests_updates(self, latest_sys_updated_on):
        """
        Constructs params for getting new Change Requests (CR) and CRs updated after the last time we queried
        ServiceNow for them. Last query time is persisted in InstanceInfo.state.latest_sys_updated_on.
        :return: dict with servicenow rest api response
        """
        reformatted_date = latest_sys_updated_on.strftime("'%Y-%m-%d', '%H:%M:%S'")
        sysparm_query = 'sys_updated_on>javascript:gs.dateGenerate(%s)' % reformatted_date
        self.log.debug('sysparm_query: %s', sysparm_query)
        return self._collect_change_requests(sysparm_query)

    def collect_planned_change_requests(self):
        """
        Constructs params for getting planned Change Requests (CR) from ServiceNow.
        CR can be planned in advance, sometimes by as much as a few months. CRs in ServiceNow have a Planned Start Date
        field that tracks this. We select CRs with Planned Start Date set for today or tomorrow.
        :return: dict with servicenow rest api response
        """
        sysparm_query = 'start_dateONToday@javascript:gs.beginningOfToday()@javascript:gs.endOfToday()' \
                        '^ORstart_dateONTomorrow@javascript:gs.beginningOfTomorrow()@javascript:gs.endOfTomorrow()'
        self.log.debug('sysparm_query: %s', sysparm_query)
        return self._collect_change_requests(sysparm_query)

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

    def _batch_collect_components(self, offset):
        """
        collect components from ServiceNow CMDB's cmdb_ci table
        (API Doc- https://developer.servicenow.com/app.do#!/rest_api_doc?v=london&id=r_TableAPI-GET)

        :return: dict, raw response from CMDB
        """
        auth = (self.user, self.password)
        cert = (self.cert, self.keyfile)
        url = self.url + API_SNOW_TABLE_CMDB_CI
        sys_class_filter_query = self._get_sys_class_component_filter_query(self.include_resource_types)
        params = self._params_append_to_sysparm_query(add_to_query=sys_class_filter_query)
        params = self._params_append_to_sysparm_query(add_to_query=self.cmdb_ci_sysparm_query,
                                                      params=params)
        params = self._prepare_json_batch_params(params, offset, self.batch_size)
        return self._get_json(url, self.timeout, params, auth, self.verify_https, cert)

    def _batch_collect_relations(self, offset):
        """
        collect relations between components from cmdb_rel_ci and publish these in batches.
        """
        auth = (self.user, self.password)
        cert = (self.cert, self.keyfile)
        url = self.url + API_SNOW_TABLE_CMDB_REL_CI
        sys_class_filter_query = self._get_sys_class_relation_filter_query(self.include_resource_types)
        params = self._params_append_to_sysparm_query(add_to_query=sys_class_filter_query)
        params = self._params_append_to_sysparm_query(add_to_query=self.cmdb_rel_ci_sysparm_query,
                                                      params=params)
        params = self._prepare_json_batch_params(params, offset, self.batch_size)
        return self._get_json(url, self.timeout, params, auth, self.verify_https, cert)

    def _batch_collect(self, collect_function):
        """
        batch processing of components or relations fetched from CMDB
        :return: collected components
        """
        offset = 0
        batch_number = 0
        completed = False
        collection = []

        while not completed:
            elements = collect_function(offset)
            if "result" in elements and isinstance(elements["result"], list):
                number_of_elements_in_current_batch = len(elements.get("result"))
            else:
                raise CheckException('Method %s has no result' % collect_function)
            completed = number_of_elements_in_current_batch < self.batch_size
            collection.extend(elements['result'])
            batch_number += 1
            offset += self.batch_size
            self.log.info(
                '%s processed batch no. %d with %d items.',
                collect_function.__name__, batch_number, number_of_elements_in_current_batch
            )

        return collection

    def _collect_change_requests(self, sysparm_query):
        """
        Prepares ServiceNow call for change request rest api endpoint.
        :param sysparm_query: custom params for rest api call
        :return: dict with servicenow rest api response
        """
        params = {
            'sysparm_display_value': 'all',
            'sysparm_exclude_reference_link': 'true',
            'sysparm_limit': self.change_request_process_limit,
            'sysparm_query': sysparm_query
        }
        params = self._params_append_to_sysparm_query(self.change_request_sysparm_query, params)
        auth = (self.user, self.password)
        cert = (self.cert, self.keyfile)
        url = self.url + API_SNOW_TABLE_CHANGE_REQUEST
        return self._get_json(url, self.timeout, params, auth, self.verify_https, cert)

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
