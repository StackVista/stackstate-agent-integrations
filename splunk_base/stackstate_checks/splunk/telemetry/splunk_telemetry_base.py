import time

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import TokenExpiredException, FinalizeException,SplunkClient
from stackstate_checks.splunk.config.splunk_instance_config import time_to_seconds, take_required_field, get_utc_time, SplunkSavedSearch, SplunkInstanceConfig, CommittableState
from stackstate_checks.splunk.saved_search_helper.saved_search_helper import chunks, SavedSearches


# TODO refactor class to reuse v2 classes

class Instance(object):
    INSTANCE_TYPE = "splunk"

    def __init__(self, instance, init_config, default_settings):
        self.instance_config = SplunkInstanceConfig(instance, init_config)
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
    date_default_fields = {'date_hour', 'date_mday', 'date_minute', 'date_month', 'date_second', 'date_wday', 'date_year', 'date_zone', 'timestartpos', 'timeendpos'}
    TIME_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"

    def __init__(self, name, init_config, agentConfig, persistence_check_name, instances=None):
        super(SplunkTelemetryBase, self).__init__(name, init_config, agentConfig, instances)
        # Data to keep over check runs, keyed by instance url
        self.persistence_check_name = persistence_check_name
        self.instance_data = dict()
        self.status = None
        self.load_status()

        # Hook to override instance creation
    def _build_instance(self, instance):
        return Instance(instance, self.init_config)

    def check(self, instance):

        if self.instance_data is None:
            self.instance_data = self._build_instance(instance)

        committable_state = CommittableState(self.commit_state, self.load_state(instance))

        instance = self.instance_data

# snapshot needed or not? self.snapshot = bool(instance.get('snapshot', True))

        try:
            instance.splunk_client.auth_session(committable_state)

            def _service_check(status, tags=None, hostname=None, message=None):
                self.service_check(self.SERVICE_CHECK_NAME, status, tags, hostname, message)

            def _process_data(saved_search, response):
                return self._extract_telemetry(instance, response)

            instance.saved_searches.run_saved_searches(_process_data, _service_check, self.log, committable_state)

            current_time = self._current_time_seconds()
            url = instance["url"]
            if url not in self.instance_data:
                self.instance_data[url] = self.get_instance(instance, current_time)

            instance = self.instance_data[url]
            if not instance.initial_time_done(current_time):
                self.log.debug("Skipping splunk metric/event instance %s, waiting for initial time to expire" % url)
                return

        except TokenExpiredException as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.tags, message=str(e.message))
            self.log.exception("Splunk event/metric exception: %s" % str(e.message))
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.tags, message=str(e))
            self.log.exception("Splunk event exception: %s" % str(e))
            if not instance.instance_config.ignore_saved_search_errors:
                raise CheckException("Error getting Splunk data, please check your configuration. Message: " + str(e))
            self.log.warning("Ignoring the exception since the flag ignore_saved_search_errors is true")

    def get_instance(self, instance, current_time):
        raise NotImplementedError

    def _log_warning(self, instance, msg):
        self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.WARNING, tags=instance.tags, message=msg)
        self.log.warn(msg)

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

# do we use it?
    def _apply(self, **kwargs):
        """ How the telemetry info should be sent by the check, e.g., as event, guage, etc. """
        raise NotImplementedError

    def _filter_fields(self, data):
        # We remove default basic fields, default date fields and internal fields that start with "_"
        return {
            key: value
            for key, value in data.iteritems()
            if self._include_as_tag(key)
        }

    def _current_time_seconds(self):
        """ This method is mocked for testing. Do not change its behavior """
        return int(round(time.time()))

    def clear_status(self):
        """
        This function is only used form test code to act as if the check is running for the first time
        """
        # TODO use new persistent state
        # CheckData.remove_latest_status(self.persistence_check_name)
        # self.load_status()

    def load_status(self):
        """load status"""
        # TODO use new persistent state
        # self.status = CheckData.load_latest_status(self.persistence_check_name)
        # if self.status is None:
        #     self.status = CheckData()

    def _include_as_tag(self, key):
        return not key.startswith('_') and key not in self.basic_default_fields.union(self.date_default_fields)

    def update_persistent_status(self, base_url, qualifier, data, action):
        """
        :param base_url: base_url of the instance
        :param qualifier: a string used for making a unique key
        :param data: data of the key
        :param action: action like remove, clear and add to perform

        This method persists the storage for the key when it is modified
        """
        # TODO use new persistent state
        # key = base_url + qualifier if qualifier else base_url
        # if action == 'remove':
        #     self.status.data.pop(key, None)
        # elif action == 'clear':
        #     self.status.data.clear()
        # else:
        #     self.status.data[key] = data
        # self.status.persist(self.persistence_check_name)
