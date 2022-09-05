import copy
import re
import time
import datetime

from six import PY3

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import FinalizeException
from stackstate_checks.splunk.config.splunk_instance_config import get_utc_time


class SavedSearches(object):
    """
    This class abstract away matching and executing saved searches on splunk. It can be constructed with configuration
    and saved searches, the saved searches can be processed by invoking run_saved_searches
    """

    def __init__(self, instance_config, splunk_client, saved_searches):
        self.instance_config = instance_config
        self.splunk_client = splunk_client
        self.searches = list(filter(lambda ss: ss.name is not None, saved_searches))
        self.matches = list(filter(lambda ss: ss.match is not None, saved_searches))

    def run_saved_searches(self, process_data, service_check, log, persisted_state, update_status=None):
        new_saved_searches = self.splunk_client.saved_searches()
        self._update_searches(log, new_saved_searches)
        all_success = True

        if callable(update_status):
            update_status()  # update transactional state

        for saved_searches_chunk in chunks(self.searches, self.instance_config.saved_searches_parallel):
            all_success &= self._dispatch_and_await_search(process_data, service_check, log, persisted_state,
                                                           saved_searches_chunk)

        if all_success:
            service_check(AgentCheck.OK)

    def _update_searches(self, log, saved_searches):  # same as v1 SavedSearches.update_searches
        """
        Take an existing list of saved searches and update the current state with that list
        :param saved_searches: List of strings with names of observed saved searches
        """
        # Drop missing matches
        self.searches = list(filter(lambda s: s.match is None or s.name in saved_searches, self.searches))

        # Filter already instantiated searches
        new_searches = set(saved_searches).difference([s.name for s in self.searches])

        # Match new searches
        for new_search in new_searches:
            for match in self.matches:
                if re.match(match.match, new_search) is not None:
                    search = copy.deepcopy(match)
                    search.name = new_search
                    log.debug("Added saved search '%s'" % new_search)
                    self.searches.append(search)
                    break

    def _dispatch_and_await_search(self, process_data, service_check, log, persisted_state, saved_searches):
        start_time = time.time()

        # don't dispatch if sids present
        for saved_search in saved_searches:
            try:
                sid = persisted_state.get_sid(saved_search.name)
                if sid is not None:
                    self.splunk_client.finalize_sid(sid, saved_search)
                    persisted_state.remove_sid(saved_search.name)
            except FinalizeException as e:
                log.exception(
                    "Got an error %s while finalizing the saved search %s" % (e.message, saved_search.name))
                if not self.instance_config.ignore_saved_search_errors:
                    raise e
                log.warning("Ignoring finalize exception as ignore_saved_search_errors flag is true.")

        search_ids = [(self._dispatch_saved_search(log, persisted_state, saved_search), saved_search)
                      for saved_search in saved_searches]

        all_success = True

        for (sid, saved_search) in search_ids:
            log.debug("Processing saved search: %s." % saved_search.name)
            if sid is None:
                log.warn("Skipping the saved search %s as it doesn't exist " % saved_search.name)
                continue
            all_success &= self._process_saved_search(process_data, service_check, log, sid, saved_search, start_time)

        return all_success

    def _process_saved_search(self, process_data, service_check, log, search_id, saved_search, start_time):
        count = 0
        fail_count = 0

        sent_events = set()
        if hasattr(saved_search, 'last_observed_telemetry'):
            sent_events = saved_search.last_observed_telemetry
            saved_search.last_observed_telemetry = set()

        try:
            responses = self.splunk_client.saved_search_results(search_id, saved_search)

            for response in responses:
                for message in response.get('messages', []):
                    if message['type'] != "FATAL" and message['type'] != "INFO":
                        log.info(
                            "Received unhandled message for saved search %s, got: %s" % (saved_search.name, message))

                count += len(response.get("results", []))
                fail_count += process_data(saved_search, response, sent_events)

            log.debug(
                "Saved search done: %s in time %d with results %d of which %d failed" % (
                    saved_search.name, time.time() - start_time, count, fail_count)
            )

            if fail_count != 0:
                if (fail_count != count) and (count != 0):
                    msg = "The saved search '%s' contained %d incomplete records" % (saved_search.name, fail_count)
                    service_check(AgentCheck.WARNING, tags=self.instance_config.tags, message=msg)
                    log.warn(msg)
                    return False
                elif count != 0:
                    raise CheckException(
                        "All result of saved search '%s' contained incomplete data" % saved_search.name)

        except CheckException as e:
            log.warning(
                "Check exception occurred %s while processing saved search name %s" % (str(e), saved_search.name))
            service_check(AgentCheck.WARNING, tags=self.instance_config.tags, message=str(e))
            if not self.instance_config.ignore_saved_search_errors:
                raise e
            return False
        except Exception as e:
            log.warning("Got an error %s while processing saved search name %s" % (str(e), saved_search.name))
            service_check(AgentCheck.WARNING, tags=self.instance_config.tags, message=str(e))
            if not self.instance_config.ignore_saved_search_errors:
                log.error("Received an exception while processing saved search " + saved_search.name)
                raise e
            return False

        return True

    def _dispatch_saved_search(self, log, persisted_state, saved_search):
        """
        Initiate a saved search, returning the search id
        :param saved_search: SavedSearch to dispatch
        :return: search id
        """
        parameters = saved_search.parameters
        # json output_mode is mandatory for response parsing
        parameters["output_mode"] = "json"

        splunk_app = saved_search.app

        log.debug("Dispatching saved search: %s." % saved_search.name)
        sid = self.splunk_client.dispatch(saved_search, splunk_app,
                                          self.instance_config.ignore_saved_search_errors,
                                          parameters)
        persisted_state.set_sid(saved_search.name, sid)
        return sid


class SavedSearchesTelemetry(SavedSearches):
    TIME_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"

    def run_saved_searches(self, process_data, service_check, log, persisted_state, update_status=None):
        new_saved_searches = self.splunk_client.saved_searches()
        self._update_searches(log, new_saved_searches)

        if callable(update_status):
            update_status()  # update transactional state

        executed_searches = False
        for saved_searches_chunk in chunks(self.searches, self.instance_config.saved_searches_parallel):
            executed_searches |= self._dispatch_and_await_search(process_data, service_check, log, persisted_state,
                                                                 saved_searches_chunk)

        if len(self.searches) != 0 and not executed_searches:
            raise CheckException("No saved search was successfully executed.")

        service_check(AgentCheck.OK)

    def _dispatch_and_await_search(self, process_data, service_check, log, persisted_state, saved_searches):
        start_time = self._current_time_seconds()
        search_ids = []

        for saved_search in saved_searches:
            try:
                sid = persisted_state.get_sid(saved_search.name)
                if sid is not None:
                    self.splunk_client.finalize_sid(sid, saved_search)
                    persisted_state.remove_sid(saved_search.name)
                sid = self._dispatch_saved_search(log, persisted_state, saved_search)
                persisted_state.set_sid(saved_search.name, sid)
                search_ids.append((sid, saved_search))
            except FinalizeException as e:
                log.exception(
                    "Got an error %s while finalizing the saved search %s" % (e.message, saved_search.name))
                if not self.instance_config.ignore_saved_search_errors:
                    raise e
                log.warning("Ignoring the finalize exception as ignore_saved_search_errors flag is true")
            except Exception as e:
                log.warning("Failed to dispatch saved search '%s' due to: %s" % (saved_search.name, e))
                service_check(AgentCheck.WARNING, tags=self.instance_config.tags, message=str(e))

        executed_searches = False
        for (sid, saved_search) in search_ids:
            try:
                log.debug("Processing saved search: %s." % saved_search.name)
                count = self._process_saved_search(process_data, service_check, log, sid, saved_search, start_time)
                duration = self._current_time_seconds() - start_time
                log.debug("Save search done: %s in time %d with results %d" % (saved_search.name, duration, count))
                executed_searches = True
            except Exception as e:
                log.warning("Failed to execute dispatched search '%s' with id %s due to: %s" %
                            (saved_search.name, sid, e))

        return executed_searches

    def _dispatch_saved_search(self, log, persisted_state, saved_search):
        parameters = saved_search.parameters
        # json output_mode is mandatory for response parsing
        parameters["output_mode"] = "json"

        earliest_epoch_datetime = get_utc_time(saved_search.last_observed_timestamp)
        splunk_app = saved_search.app

        parameters["dispatch.time_format"] = self.TIME_FMT
        parameters["dispatch.earliest_time"] = earliest_epoch_datetime.strftime(self.TIME_FMT)

        if "dispatch.latest_time" in parameters:
            del parameters["dispatch.latest_time"]

        # Always observe the last time for data and use max query chunk seconds
        latest_time_epoch = saved_search.last_observed_timestamp + saved_search.config['max_query_chunk_seconds']

        _last_observed = datetime.datetime.utcfromtimestamp(saved_search.last_observed_timestamp).strftime('%Y-%m-%dT%H:%M:%SZ')
        _real_value = datetime.datetime.utcfromtimestamp(latest_time_epoch).strftime('%Y-%m-%dT%H:%M:%SZ')

        current_time = self._current_time_seconds()

        if latest_time_epoch >= current_time:
            log.info("[CONTINUE] Caught up with old splunk data for saved search %s since %s" % (
                saved_search.name, parameters["dispatch.earliest_time"]))
            saved_search.last_recover_latest_time_epoch_seconds = None
        else:
            saved_search.last_recover_latest_time_epoch_seconds = latest_time_epoch
            latest_epoch_datetime = get_utc_time(latest_time_epoch)
            parameters["dispatch.latest_time"] = latest_epoch_datetime.strftime(self.TIME_FMT)
            log.info("[CATCH_UP] Catching up with old splunk data for saved search %s from %s to %s " % (
                saved_search.name, parameters["dispatch.earliest_time"], parameters["dispatch.latest_time"]))

        log.debug(
            "Dispatching saved search: %s starting at %s." % (saved_search.name, parameters["dispatch.earliest_time"]))

        sid = self.splunk_client.dispatch(saved_search, splunk_app,
                                          self.instance_config.ignore_saved_search_errors,
                                          parameters)
        persisted_state.set_sid(saved_search.name, sid)
        return sid

    @staticmethod
    def _current_time_seconds():
        """ This method is mocked for testing. Do not change its behavior """
        return int(round(time.time()))


def chunks(original_list, n):
    """Yield successive n-sized chunks from list."""
    if PY3:
        for i in range(0, len(original_list), n):
            yield original_list[i:i + n]
    else:
        for i in xrange(0, len(original_list), n):  # noqa: F821
            yield original_list[i:i + n]
