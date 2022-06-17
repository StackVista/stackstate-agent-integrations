from stackstate_checks.base import AgentCheck, TopologyInstance
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import SplunkClient, TokenExpiredException
from stackstate_checks.splunk.config import SplunkInstanceConfig, SplunkSavedSearch, CommittableState
from stackstate_checks.splunk.saved_search_helper import SavedSearches

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


class Instance(object):
    INSTANCE_TYPE = "splunk"

    def __init__(self, instance, init_config):
        self.instance_config = SplunkInstanceConfig(instance, init_config, default_settings)
        self.splunk_client = self._build_splunk_client()

        # transform component and relation saved searches to SavedSearch objects
        saved_searches = [SplunkSavedSearch(self.instance_config, saved_search_instance)
                          for saved_search_instance in instance.get('saved_searches', [])]

        self.saved_searches = SavedSearches(self.instance_config, self.splunk_client, saved_searches)

    # Hook to allow for mocking
    def _build_splunk_client(self):
        return SplunkClient(self.instance_config)

class SplunkMetric(AgentCheck):
    SERVICE_CHECK_NAME = "splunk.metric_information"

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SplunkMetric, self).__init__(name, init_config, agentConfig, instances)
        # Data to keep over check runs
        self.instance_data = None

    def get_instance_key(self, instance):
        return TopologyInstance(Instance.INSTANCE_TYPE, instance["url"])

    # Hook to override instance creation
    def _build_instance(self, instance):
        return Instance(instance, self.init_config)

    def check(self, instance):
        if self.instance_data is None:
            self.instance_data = self._build_instance(instance)

        committable_state = CommittableState(self.commit_state, self.load_state(instance))

        instance = self.instance_data

        self.health.start_snapshot()

        try:
            instance.splunk_client.auth_session(committable_state)

            def _service_check(status, tags=None, hostname=None, message=None):
                self.service_check(self.SERVICE_CHECK_NAME, status, tags, hostname, message)

            def _process_data(saved_search, response):
                return self._extract_metric(instance, response)

            instance.saved_searches.run_saved_searches(_process_data, _service_check, self.log, committable_state)

            self.health.stop_snapshot()
        except TokenExpiredException as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.instance_config.tags,
                               message=str(e.message))
            self.log.exception("Splunk health exception: %s" % str(e))
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.instance_config.tags,
                               message=str(e))
            self.log.exception("Splunk health exception: %s" % str(e))
            if not instance.instance_config.ignore_saved_search_errors:
                raise CheckException("Splunk health failed with message: %s" % e, None, sys.exc_info()[2])

    def _extract_metric(self, instance, result):
        fail_count = 0

        for data in result["results"]:
            check_state_id = data.get("check_state_id")
            name = data.get("name")
            health = None
            try:
                health = HealthType().convert(data.get("health"), None)
            except ValidationError:
                pass
            topology_element_identifier = data.get("topology_element_identifier")
            message = data.get("message", None)

            if check_state_id is not None and \
                    name is not None and \
                    health is not None and \
                    topology_element_identifier is not None:
                self.health.check_state(check_state_id, name, health, topology_element_identifier, message)
            else:
                fail_count += 1

        return fail_count