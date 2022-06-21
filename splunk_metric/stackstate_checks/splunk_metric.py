from stackstate_checks.splunk.telemetry.splunk_telemetry_base import SplunkTelemetryBase, SplunkTelemetryBaseInstance

default_settings = {
    'default_request_timeout_seconds': 5,
    'default_search_max_retry_count': 3,
    'default_search_seconds_between_retries': 1,
    'default_verify_ssl_certificate': False,
    'default_batch_size': 1000,
    'default_saved_searches_parallel': 3,
    "default_metric_name_field": "metric",
    "default_metric_value_field": "value",
    'default_initial_history_time_seconds': 0,
    'default_max_restart_history_seconds': 86400,
    'default_max_query_chunk_seconds': 300,
    'default_initial_delay_seconds': 0,
    'default_unique_key_fields': ["_bkt", "_cd"],
    'default_app': "search",
    'default_parameters': {
        "force_dispatch": True,
        "dispatch.now": True
    }
}

class SplunkMetric(SplunkTelemetryBase):
    SERVICE_CHECK_NAME = "splunk.metric_information"

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SplunkMetric, self).__init__(name, init_config, agentConfig, instances)
        # Data to keep over check runs
        self.instance_data = None

    # Hook to override instance creation
    def _build_instance(self, instance):
        return SplunkTelemetryBaseInstance(instance, self.init_config)

    def _apply(self, metric, value, **kwargs):
        self.raw(metric, float(value), **kwargs)
