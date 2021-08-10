API_SNOW_TABLE_CMDB_CI = '/api/now/table/cmdb_ci'
API_SNOW_TABLE_CMDB_REL_CI = '/api/now/table/cmdb_rel_ci'
API_SNOW_TABLE_CHANGE_REQUEST = '/api/now/table/change_request'
BATCH_DEFAULT_SIZE = 2500
BATCH_MAX_SIZE = 10000
TIMEOUT = 20
VERIFY_HTTPS = True
CRS_BOOTSTRAP_DAYS_DEFAULT = 100
CRS_DEFAULT_PROCESS_LIMIT = 1000
CMDB_CI_DEFAULT_FIELD = 'cmdb_ci'
CR_PLANNED_RESEND_SCHEDULE_IN_HOURS_DEFAULT = 1
CR_PLANNED_START_DATE_DEFAULT_FIELD = 'start_date'
CR_PLANNED_END_DATE_DEFAULT_FIELD = 'end_date'

# keys for which `display_value` has to be used
DEFAULT_COMPONENT_DISPLAY_VALUE_LIST = [
    "sys_tags", "maintenance_schedule", "location", "company", "manufacturer", "vendor"
]
DEFAULT_RELATION_DISPLAY_VALUE_LIST = ["sys_tags", "type"]
