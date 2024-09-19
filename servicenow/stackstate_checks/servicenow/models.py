from stackstate_checks.base.utils.validations_utils import ForgivingBaseModel, AnyUrlStr, StrictBaseModel
from stackstate_checks.servicenow.common import DEFAULT_COMPONENT_DISPLAY_VALUE_LIST, \
    DEFAULT_RELATION_DISPLAY_VALUE_LIST, BATCH_DEFAULT_SIZE, BATCH_MAX_SIZE, TIMEOUT, VERIFY_HTTPS, \
    CRS_BOOTSTRAP_DAYS_DEFAULT, CRS_DEFAULT_PROCESS_LIMIT, CMDB_CI_DEFAULT_FIELD, \
    CR_PLANNED_RESEND_SCHEDULE_IN_HOURS_DEFAULT, CR_PLANNED_START_DATE_DEFAULT_FIELD, CR_PLANNED_END_DATE_DEFAULT_FIELD
from datetime import datetime
from typing import Optional, List
from pydantic import Field


class WrapperStringType(ForgivingBaseModel):
    value: str = ''
    display_value: str = ''


class WrapperDateType(ForgivingBaseModel):
    value: Optional[datetime] = None
    display_value: Optional[datetime] = None


class ChangeRequest(ForgivingBaseModel):
    number: WrapperStringType
    state: WrapperStringType
    custom_cmdb_ci: WrapperStringType
    sys_updated_on: WrapperDateType
    business_service: Optional[WrapperStringType] = None
    service_offering: Optional[WrapperStringType] = None
    short_description: Optional[WrapperStringType] = None
    description: Optional[WrapperStringType] = None
    type: Optional[WrapperStringType] = None
    priority: Optional[WrapperStringType] = None
    impact: Optional[WrapperStringType] = None
    risk: Optional[WrapperStringType] = None
    requested_by: Optional[WrapperStringType] = None
    category: Optional[WrapperStringType] = None
    conflict_status: Optional[WrapperStringType] = None
    conflict_last_run: Optional[WrapperStringType] = None
    assignment_group: Optional[WrapperStringType] = None
    assigned_to: Optional[WrapperStringType] = None
    custom_planned_start_date: Optional[WrapperStringType] = None
    custom_planned_end_date: Optional[WrapperStringType] = None


class ConfigurationItem(ForgivingBaseModel):
    name: WrapperStringType
    sys_class_name: WrapperStringType
    sys_id: WrapperStringType
    sys_tags: WrapperStringType = WrapperStringType()
    fqdn: WrapperStringType = WrapperStringType()
    host_name: WrapperStringType = WrapperStringType()


class CIRelation(ForgivingBaseModel):
    sys_id: Optional[WrapperStringType] = None
    connection_strength: Optional[WrapperStringType] = None
    parent: WrapperStringType
    sys_mod_count: Optional[WrapperStringType] = None
    sys_tags: WrapperStringType = WrapperStringType()
    type: WrapperStringType
    port: Optional[WrapperStringType] = None
    percent_outage: Optional[WrapperStringType] = None
    child: WrapperStringType


class State(StrictBaseModel):
    latest_sys_updated_on: datetime
    change_requests: dict = {}
    sent_planned_crs_cache: List[str] = []


class InstanceInfo(ForgivingBaseModel):
    url: AnyUrlStr
    user: str
    password: str
    include_resource_types: List[str] = []
    component_display_value_list: List[str] = DEFAULT_COMPONENT_DISPLAY_VALUE_LIST
    relation_display_value_list: List[str] = DEFAULT_RELATION_DISPLAY_VALUE_LIST
    batch_size: int = Field(default=BATCH_DEFAULT_SIZE, le=BATCH_MAX_SIZE)
    timeout: int = TIMEOUT
    verify_https: bool = VERIFY_HTTPS
    cert: Optional[str] = None
    keyfile: Optional[str] = None
    instance_tags: List[str] = []
    change_request_bootstrap_days: int = CRS_BOOTSTRAP_DAYS_DEFAULT
    change_request_process_limit: int = CRS_DEFAULT_PROCESS_LIMIT
    cmdb_ci_sysparm_query: Optional[str] = None
    cmdb_rel_ci_sysparm_query: Optional[str] = None
    change_request_sysparm_query: Optional[str] = None
    custom_cmdb_ci_field: str = CMDB_CI_DEFAULT_FIELD
    planned_change_request_resend_schedule: int = CR_PLANNED_RESEND_SCHEDULE_IN_HOURS_DEFAULT
    custom_planned_start_date_field: str = CR_PLANNED_START_DATE_DEFAULT_FIELD
    custom_planned_end_date_field: str = CR_PLANNED_END_DATE_DEFAULT_FIELD
    state: Optional[State] = None
