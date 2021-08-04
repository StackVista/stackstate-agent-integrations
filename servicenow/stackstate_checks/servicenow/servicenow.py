# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime

from schematics.exceptions import DataError

from stackstate_checks.base import AgentCheck, StackPackInstance, Identifiers, to_string
from stackstate_checks.servicenow import State, InstanceInfo
from stackstate_checks.servicenow.client import ServiceNowClient
from stackstate_checks.servicenow.models import ChangeRequest, ConfigurationItem, CIRelation


class ServiceNowCheck(AgentCheck):
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
            snow_client = ServiceNowClient(instance_info)
            self.start_snapshot()
            self._process_components(snow_client, instance_info)
            self._process_relations(snow_client, instance_info)
            self._process_change_requests(snow_client, instance_info)
            self._process_planned_change_requests(snow_client, instance_info)
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

    @staticmethod
    def _select_metadata_field(data, display_value_list):
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

    def _process_components(self, client, instance_info):
        """
        Gets SNOW components name, external_id and other identifiers
        :param instance_info:
        :return: None
        """
        collected_components = client.collect_components()

        for component in collected_components:
            try:
                config_item = ConfigurationItem(component, strict=False)
                config_item.validate()
            except DataError as e:
                self.log.warning("Error while processing properties of CI {} having sys_id {} - {}"
                                 .format(config_item.sys_id.value, config_item.name.value, e))
                continue
            data = {}
            component = self._select_metadata_field(component, instance_info.component_display_value_list)
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

    def _process_relations(self, client, instance_info):
        """
        process relations
        """
        collected_relations = client.collect_relations()
        for relation in collected_relations:
            try:
                ci_relation = CIRelation(relation, strict=False)
                ci_relation.validate()
            except DataError as e:
                self.log.warning("Error while processing properties of relation having Sys ID {} - {}"
                                 .format(ci_relation.sys_id.value, e))
                continue
            data = {}
            relation = self._select_metadata_field(relation, instance_info.relation_display_value_list)
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

    def _process_change_requests(self, client, instance_info):
        """
        Change Requests (CR) need to fit the following criteria to be send to StackState as Topology Event:
        - new CR that is created after last time we queried ServiceNow
        - existing CR that is updated after last time we queried ServiceNow and their State has changed
        :param instance_info: Instance object
        :return: None
        """
        number_of_new_crs = 0
        self.log.debug('Begin processing change requests.')
        response_new_crs = client.collect_change_requests_updates(instance_info.state.latest_sys_updated_on)
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

    def _process_planned_change_requests(self, client, instance_info):
        """
        Planned Change Requests (CR) were created in the past, and they are due today so we resend them 1 hour before
        their Planned Start Date. 1 hour is default value. It can be changed in check config.
        InstanceInfo.state.planned_change_requests_cache holds list of sent Planned CRs so we don't resend them.
        :param instance_info: Instance object
        :return: None
        """
        number_of_planned_crs = 0
        self.log.debug('Begin processing planned change requests.')
        response_planned_crs = client.collect_planned_change_requests()
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
