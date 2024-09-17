CheckBaseModel
from schematics.types import StringType, DateTimeType, ModelType, DictType, ListType, URLType, IntType, BooleanType

from stackstate_checks.servicenow.common import DEFAULT_COMPONENT_DISPLAY_VALUE_LIST, \
    DEFAULT_RELATION_DISPLAY_VALUE_LIST, BATCH_DEFAULT_SIZE, BATCH_MAX_SIZE, TIMEOUT, VERIFY_HTTPS, \
    CRS_BOOTSTRAP_DAYS_DEFAULT, CRS_DEFAULT_PROCESS_LIMIT, CMDB_CI_DEFAULT_FIELD, \
    CR_PLANNED_RESEND_SCHEDULE_IN_HOURS_DEFAULT, CR_PLANNED_START_DATE_DEFAULT_FIELD, CR_PLANNED_END_DATE_DEFAULT_FIELD


class WrapperStringType(Model):
    value = StringType(default='')
    display_value = StringType(default='')


class WrapperDateType(Model):
    value = DateTimeType()
    display_value = DateTimeType()


class ChangeRequest(Model):
    number = ModelType(WrapperStringType, required=True)
    state = ModelType(WrapperStringType, required=True)
    custom_cmdb_ci = ModelType(WrapperStringType, required=True)
    sys_updated_on = ModelType(WrapperDateType, required=True)
    business_service = ModelType(WrapperStringType)
    service_offering = ModelType(WrapperStringType)
    short_description = ModelType(WrapperStringType)
    description = ModelType(WrapperStringType)
    type = ModelType(WrapperStringType)
    priority = ModelType(WrapperStringType)
    impact = ModelType(WrapperStringType)
    risk = ModelType(WrapperStringType)
    requested_by = ModelType(WrapperStringType)
    category = ModelType(WrapperStringType)
    conflict_status = ModelType(WrapperStringType)
    conflict_last_run = ModelType(WrapperStringType)
    assignment_group = ModelType(WrapperStringType)
    assigned_to = ModelType(WrapperStringType)
    custom_planned_start_date = ModelType(WrapperStringType)
    custom_planned_end_date = ModelType(WrapperStringType)


class ConfigurationItem(Model):
    name = ModelType(WrapperStringType, required=True)
    sys_class_name = ModelType(WrapperStringType, required=True)
    sys_id = ModelType(WrapperStringType, required=True)
    sys_tags = ModelType(WrapperStringType, default=WrapperStringType())
    fqdn = ModelType(WrapperStringType, default=WrapperStringType())
    host_name = ModelType(WrapperStringType, default=WrapperStringType())


class CIRelation(Model):
    sys_id = ModelType(WrapperStringType)
    connection_strength = ModelType(WrapperStringType)
    parent = ModelType(WrapperStringType, required=True)
    sys_mod_count = ModelType(WrapperStringType)
    sys_tags = ModelType(WrapperStringType, default=WrapperStringType())
    type = ModelType(WrapperStringType, required=True)
    port = ModelType(WrapperStringType)
    percent_outage = ModelType(WrapperStringType)
    child = ModelType(WrapperStringType, required=True)


class State(Model):
    latest_sys_updated_on = DateTimeType(required=True)
    change_requests = DictType(StringType, default={})
    sent_planned_crs_cache = ListType(StringType, default=[])


class InstanceInfo(Model):
    url = URLType(required=True)
    user = StringType(required=True)
    password = StringType(required=True)
    include_resource_types = ListType(StringType, default=[])
    component_display_value_list = ListType(StringType, default=DEFAULT_COMPONENT_DISPLAY_VALUE_LIST)
    relation_display_value_list = ListType(StringType, default=DEFAULT_RELATION_DISPLAY_VALUE_LIST)
    batch_size = IntType(default=BATCH_DEFAULT_SIZE, max_value=BATCH_MAX_SIZE)
    timeout = IntType(default=TIMEOUT)
    verify_https = BooleanType(default=VERIFY_HTTPS)
    cert = StringType()
    keyfile = StringType()
    instance_tags = ListType(StringType, default=[])
    change_request_bootstrap_days = IntType(default=CRS_BOOTSTRAP_DAYS_DEFAULT)
    change_request_process_limit = IntType(default=CRS_DEFAULT_PROCESS_LIMIT)
    cmdb_ci_sysparm_query = StringType()
    cmdb_rel_ci_sysparm_query = StringType()
    change_request_sysparm_query = StringType()
    custom_cmdb_ci_field = StringType(default=CMDB_CI_DEFAULT_FIELD)
    planned_change_request_resend_schedule = IntType(default=CR_PLANNED_RESEND_SCHEDULE_IN_HOURS_DEFAULT)
    custom_planned_start_date_field = StringType(default=CR_PLANNED_START_DATE_DEFAULT_FIELD)
    custom_planned_end_date_field = StringType(default=CR_PLANNED_END_DATE_DEFAULT_FIELD)
    state = ModelType(State)
