from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.config import SplunkSavedSearch
from stackstate_checks.splunk.saved_search_helper import SavedSearchesTelemetry


class SplunkTelemetrySavedSearch(SplunkSavedSearch):
    last_events_at_epoch_time = set()

    def __init__(self, instance_config, saved_search_instance):
        super(SplunkTelemetrySavedSearch, self).__init__(instance_config, saved_search_instance)

        self.unique_key_fields = saved_search_instance.get('unique_key_fields',
                                                           instance_config.default_unique_key_fields)

        self.config = {
            field_name: saved_search_instance.get(field_name, instance_config.get_or_default("default_" + field_name))
            for field_name in ['initial_history_time_seconds', 'max_restart_history_seconds', 'max_query_chunk_seconds']
        }

        # Up until which timestamp did we get with the data?
        self.last_observed_timestamp = 0

        # End of the last recovery time window. When this is None recovery is done. 0 signifies uninitialized.
        # Any value above zero signifies until what time we recovered.
        self.last_recover_latest_time_epoch_seconds = 0

        # We keep track of the events that were reported for the last timestamp, to deduplicate them when
        # we get a new query
        self.last_observed_telemetry = set()

    def get_status(self):
        """
        :return: Return a tuple of the last time until which the query was run, and whether this was based on history
        """

        if self.last_recover_latest_time_epoch_seconds is None:
            # If there is not catching up to do, the status is as far as the last event time
            return self.last_observed_timestamp, False
        else:
            # If we are still catching up, we got as far as the last finish time. We report as
            # inclusive bound (hence the -1)
            return self.last_recover_latest_time_epoch_seconds - 1, True


class SplunkTelemetryInstance(object):
    INSTANCE_TYPE = "splunk"

    def __init__(self, current_time, instance, instance_config, create_saved_search):
        self.instance_config = instance_config
        self.splunk_client = self._build_splunk_client()

        self.saved_searches = SavedSearchesTelemetry(instance_config, self.splunk_client, [
                                                     create_saved_search(instance_config, saved_search_instance)
                                                     for saved_search_instance in instance['saved_searches']
                                                     ])

        self.saved_searches_parallel = int(instance.get('saved_searches_parallel', self.instance_config.get_or_default(
            'default_saved_searches_parallel')))
        self.tags = instance.get('tags', [])
        self.initial_delay_seconds = int(
            instance.get('initial_delay_seconds', self.instance_config.get_or_default('default_initial_delay_seconds')))
        self.launch_time_seconds = current_time
        self.unique_key_fields = instance.get('unique_key_fields',
                                              self.instance_config.get_or_default('default_unique_key_fields'))

    # Hook to allow for mocking
    def _build_splunk_client(self):
        return SplunkClient(self.instance_config)

    def initial_time_done(self, current_time_seconds):
        return current_time_seconds >= self.launch_time_seconds + self.initial_delay_seconds

    def get_status(self):
        """
        :return: Aggregate the status for saved searches and report whether there were historical queries among it.
        """
        status_dict = dict()
        has_history = False

        for saved_search in self.saved_searches.searches:
            (secs, was_history) = saved_search.get_status()
            status_dict[saved_search.name] = secs
            has_history = has_history or was_history

        return status_dict, has_history

    def get_search_data(self, data, search):
        if search in data:
            return data[search]
        else:
            return None

    def update_status(self, current_time, data):
        for saved_search in self.saved_searches.searches:
            # Do we need to recover?
            last_committed = self.get_search_data(data, saved_search.name)
            if last_committed is None:  # Is this the first time we start?
                saved_search.last_observed_timestamp = current_time - saved_search.config[
                    'initial_history_time_seconds']
            else:  # Continue running or restarting, add one to not duplicate the last events.
                saved_search.last_observed_timestamp = last_committed + 1
                max_restart_history_seconds = saved_search.config['max_restart_history_seconds']
                if current_time - saved_search.last_observed_timestamp > max_restart_history_seconds:
                    saved_search.last_observed_timestamp = current_time - max_restart_history_seconds
