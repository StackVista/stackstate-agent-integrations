"""
    Metrics from splunk. StackState.
"""

# 3rd party
from stackstate_checks.splunk.config.splunk_instance_config import SplunkTelemetryInstanceConfig
from stackstate_checks.splunk.telemetry.splunk_telemetry import SplunkTelemetrySavedSearch, SplunkTelemetryInstance
from stackstate_checks.splunk.telemetry.splunk_telemetry_base import SplunkTelemetryBase


class MetricSavedSearch(SplunkTelemetrySavedSearch):
    last_observed_telemetry = set()

    # how fields are to be specified in the config
    field_name_in_config = {
        'metric': 'metric_name_field',
        'value': 'metric_value_field',
    }

    def __init__(self, instance_config, saved_search_instance):
        super(MetricSavedSearch, self).__init__(instance_config, saved_search_instance)

        required_base_fields = ['value']

        if 'metric_name' in saved_search_instance and saved_search_instance['metric_name'] is not None:
            if 'metric_name_field' in saved_search_instance and saved_search_instance['metric_name_field'] is not None:
                raise Exception("Cannot set both metric_name and metric_name_field")

            self.fixed_fields = {'metric': saved_search_instance.get('metric_name')}
        else:
            required_base_fields.append('metric')

        if self.required_fields is None:
            self.required_fields = {}

        for field_name in required_base_fields:
            for name_in_config in [MetricSavedSearch.field_name_in_config.get(field_name, field_name)]:
                metric_value = saved_search_instance.get(name_in_config)

                # Check None allows us to use Non in schematics to pass certain functionality
                # If the key does not exist get the default_ value
                if metric_value is None:
                    metric_value = instance_config.get_or_default("default_" + name_in_config)

                self.required_fields[field_name] = metric_value


class SplunkMetric(SplunkTelemetryBase):
    CHECK_NAME = "splunk.metric_information"
    SERVICE_CHECK_NAME = "splunk.metric_information"

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SplunkMetric, self).__init__(name, init_config, agentConfig, instances)

    def _apply(self, metric, value, **kwargs):
        tags = kwargs.get("tags")
        hostname = kwargs.get("hostname")
        device_name = kwargs.get("device_name")
        timestamp = kwargs.get("timestamp")

        self.raw(metric, float(value), tags, hostname, device_name, int(timestamp))

    def get_instance(self, instance, current_time):
        metric_instance_config = SplunkTelemetryInstanceConfig(instance, self.init_config, {
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
        })

        # method to be overwritten by SplunkMetric and SplunkEvent
        def _create_saved_search(instance_config, saved_search_instance):
            return MetricSavedSearch(instance_config, saved_search_instance)

        return self._build_instance(current_time, instance, metric_instance_config, _create_saved_search)

    def _build_instance(self, current_time, instance, metric_instance_config, _create_saved_search):
        return SplunkTelemetryInstance(current_time, instance, metric_instance_config,
                                       _create_saved_search)
