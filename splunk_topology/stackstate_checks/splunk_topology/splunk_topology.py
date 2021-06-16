"""
    StackState.
    Splunk topology extraction
"""

# 3rd party
import sys

from stackstate_checks.base import AgentCheck, TopologyInstance
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import TokenExpiredException, SplunkClient

from stackstate_checks.splunk.config.splunk_instance_config import SplunkSavedSearch, SplunkInstanceConfig, \
    CommittableState, take_optional_field
from stackstate_checks.splunk.saved_search_helper import SavedSearches


class SavedSearch(SplunkSavedSearch):
    def __init__(self, element_type, instance_config, saved_search_instance):
        super(SavedSearch, self).__init__(instance_config, saved_search_instance)
        self.element_type = element_type


class InstanceConfig(SplunkInstanceConfig):
    def __init__(self, instance, init_config):
        super(InstanceConfig, self).__init__(instance, init_config, {
            'default_request_timeout_seconds': 5,
            'default_search_max_retry_count': 3,
            'default_search_seconds_between_retries': 1,
            'default_verify_ssl_certificate': False,
            'default_batch_size': 1000,
            'default_saved_searches_parallel': 3,
            'default_app': "search",
            'default_parameters': {
                "force_dispatch": True,
                "dispatch.now": True
            }
        })

        if 'default_polling_interval_seconds' in init_config:
            raise CheckException(
                "deprecated config `init_config.default_polling_interval_seconds` found."
                " Please use the new init_config.min_collection_interval.")


class Instance(object):
    INSTANCE_TYPE = "splunk"

    def __init__(self, instance, init_config):
        self.instance_config = InstanceConfig(instance, init_config)
        self.splunk_client = self._build_splunk_client()

        self.snapshot = bool(instance.get('snapshot', True))

        # no saved searches may be configured
        if not isinstance(instance['component_saved_searches'], list):
            instance['component_saved_searches'] = []
        if not isinstance(instance['relation_saved_searches'], list):
            instance['relation_saved_searches'] = []

        # transform component and relation saved searches to SavedSearch objects
        components = [SavedSearch("component", self.instance_config, saved_search_instance)
                      for saved_search_instance in instance['component_saved_searches']]
        relations = [SavedSearch("relation", self.instance_config, saved_search_instance)
                     for saved_search_instance in instance['relation_saved_searches']]

        self.saved_searches = SavedSearches(self.instance_config, self.splunk_client, components + relations)

        if 'polling_interval_seconds' in instance:
            raise CheckException(
                "deprecated config `polling_interval_seconds` found. Please use the new min_collection_interval.")

    # Hook to allow for mocking
    def _build_splunk_client(self):
        return SplunkClient(self.instance_config)


class SplunkTopology(AgentCheck):
    SERVICE_CHECK_NAME = "splunk.topology_information"
    EXCLUDE_FIELDS = set(['_raw', '_indextime', '_cd', '_serial', '_sourcetype', '_bkt', '_si'])

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SplunkTopology, self).__init__(name, init_config, agentConfig, instances)
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

        if instance.snapshot:
            self.start_snapshot()

        try:
            instance.splunk_client.auth_session(committable_state)

            def _service_check(status, tags=None, hostname=None, message=None):
                self.service_check(self.SERVICE_CHECK_NAME, status, tags, hostname, message)

            def _process_data(saved_search, response):
                if saved_search.element_type == "component":
                    return self._extract_components(instance, response)
                elif saved_search.element_type == "relation":
                    return self._extract_relations(instance, response)

            instance.saved_searches.run_saved_searches(_process_data, _service_check, self.log, committable_state)

            if instance.snapshot:
                self.stop_snapshot()
        except TokenExpiredException as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.instance_config.tags,
                               message=str(e.message))
            self.log.exception("Splunk topology exception: %s" % str(e))
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.instance_config.tags,
                               message=str(e))
            self.log.exception("Splunk topology exception: %s" % str(e))
            if not instance.instance_config.ignore_saved_search_errors:
                raise CheckException("Splunk topology failed with message: %s" % e, None, sys.exc_info()[2])

    def _extract_components(self, instance, result):
        fail_count = 0

        for data in result["results"]:
            # Required fields
            external_id = take_optional_field("id", data)
            comp_type = take_optional_field("type", data)

            # Add tags to data
            if 'tags' in data and instance.instance_config.tags:
                data['tags'] += instance.instance_config.tags
            elif instance.instance_config.tags:
                data['tags'] = instance.instance_config.tags

            # We don't want to present all fields
            filtered_data = self._filter_fields(data)

            if external_id is not None and comp_type is not None:
                self.component(external_id, comp_type, filtered_data)
            else:
                fail_count += 1

        return fail_count

    def _extract_relations(self, instance, result):
        fail_count = 0

        for data in result["results"]:
            # Required fields
            rel_type = take_optional_field("type", data)
            source_id = take_optional_field("sourceId", data)
            target_id = take_optional_field("targetId", data)

            # Add tags to data
            if 'tags' in data and instance.instance_config.tags:
                data['tags'] += instance.instance_config.tags
            elif instance.instance_config.tags:
                data['tags'] = instance.instance_config.tags

            # We don't want to present all fields
            filtered_data = self._filter_fields(data)

            if rel_type is not None and source_id is not None and target_id is not None:
                self.relation(source_id, target_id, rel_type, filtered_data)
            else:
                fail_count += 1

        return fail_count

    def _filter_fields(self, data):
        result = dict()
        for key, value in data.items():
            if key not in self.EXCLUDE_FIELDS:
                result[key] = value
        return result

    def load_state(self, instance):
        state = instance.get(self.STATE_FIELD_NAME)
        if state is None:
            state = {}
        return state
