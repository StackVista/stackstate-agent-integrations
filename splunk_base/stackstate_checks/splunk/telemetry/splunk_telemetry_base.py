import sys

from stackstate_checks.base import AgentCheck, TopologyInstance
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import TokenExpiredException, SplunkClient
from stackstate_checks.splunk.config import CommittableState
from stackstate_checks.splunk.config.splunk_instance_config import time_to_seconds, take_required_field, \
    SplunkInstanceConfig, SplunkSavedSearch
from stackstate_checks.splunk.saved_search_helper.saved_search_helper import SavedSearches


# TODO refactor class to reuse v2 classes

class SplunkTelemetryBaseInstance(object):
    INSTANCE_TYPE = "splunk"

    def __init__(self, instance, init_config, default_settings):
        self.instance_config = SplunkInstanceConfig(instance, init_config, default_settings)
        self.splunk_client = self._build_splunk_client()

        # transform component and relation saved searches to SavedSearch objects
        saved_searches = [SplunkSavedSearch(self.instance_config, saved_search_instance)
                          for saved_search_instance in instance.get('saved_searches', [])]

        self.saved_searches = SavedSearches(self.instance_config, self.splunk_client, saved_searches)

    # Hook to allow for mocking
    def _build_splunk_client(self):
        return SplunkClient(self.instance_config)


class SplunkTelemetryBase(AgentCheck):
    SERVICE_CHECK_NAME = None  # must be set in the subclasses
    basic_default_fields = {'index', 'linecount', 'punct', 'source', 'sourcetype', 'splunk_server', 'timestamp'}
    date_default_fields = {'date_hour', 'date_mday', 'date_minute', 'date_month', 'date_second', 'date_wday',
                           'date_year', 'date_zone', 'timestartpos', 'timeendpos'}
    TIME_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SplunkTelemetryBase, self).__init__(name, init_config, agentConfig, instances)
        # Data to keep over check runs
        self.instance_data = None

    def get_instance_key(self, instance):
        return TopologyInstance(SplunkTelemetryBaseInstance.INSTANCE_TYPE, instance["url"])

    # Hook to override instance creation
    def _build_instance(self, instance):
        """ Build instance object with default settings. """
        raise NotImplementedError
        # return SplunkTelemetryBaseInstance(instance, self.init_config, default_settings)

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
                return self._extract_telemetry(saved_search, instance, response)

            instance.saved_searches.run_saved_searches(_process_data, _service_check, self.log, committable_state)

            self.health.stop_snapshot()
        except TokenExpiredException as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.instance_config.tags,
                               message=str(e.message))
            self.log.exception("Splunk metric exception: %s" % str(e))
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.instance_config.tags,
                               message=str(e))
            self.log.exception("Splunk metric exception: %s" % str(e))
            if not instance.instance_config.ignore_saved_search_errors:
                raise CheckException("Splunk metric failed with message: %s" % e, None, sys.exc_info()[2])

    def _extract_telemetry(self, saved_search, instance, result, sent_already):
        for data in result["results"]:
            # We need a unique identifier for splunk events, according to https://answers.splunk.com/answers/334613/is-there-a-unique-event-id-for-each-event-in-the-i.html
            # this can be (server, index, _cd)

            try:
                if not saved_search.unique_key_fields:  # empty list, whole record
                    current_id = tuple(data)
                else:
                    current_id = tuple(data[field] for field in saved_search.unique_key_fields)

                timestamp = time_to_seconds(take_required_field("_time", data))

                if timestamp > saved_search.last_observed_timestamp:
                    saved_search.last_observed_telemetry = {current_id}  # make a new set
                    saved_search.last_observed_timestamp = timestamp
                elif timestamp == saved_search.last_observed_timestamp:
                    saved_search.last_observed_telemetry.add(current_id)

                if current_id in sent_already:
                    continue

                telemetry = saved_search.retrieve_fields(data)
                event_tags = [
                    "%s:%s" % (key, value)
                    for key, value in self._filter_fields(data).iteritems()
                ]
                event_tags.extend(instance.tags)
                telemetry.update({"tags": event_tags, "timestamp": timestamp})
                yield telemetry
            except Exception as e:
                self.log.exception(e)
                yield None

    def _filter_fields(self, data):
        # We remove default basic fields, default date fields and internal fields that start with "_"
        return {
            key: value
            for key, value in data.iteritems()
            if self._include_as_tag(key)
        }

    def _include_as_tag(self, key):
        return not key.startswith('_') and key not in self.basic_default_fields.union(self.date_default_fields)

    def load_state(self, instance):
        state = instance.get(self.STATE_FIELD_NAME)
        if state is None:
            state = {}
        return state
