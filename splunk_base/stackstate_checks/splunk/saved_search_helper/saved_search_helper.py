import re
import copy
import time

from six import PY3
from stackstate_checks.base.errors import CheckException
from stackstate_checks.base import AgentCheck
from stackstate_checks.splunk.client import FinalizeException


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

    @staticmethod
    def _default_update_status(log):
        log.debug("Called _default_update_status. Noop.")

    def run_saved_searches(self, process_data, service_check, log, persisted_state, update_status=_default_update_status):
        new_saved_searches = self.splunk_client.saved_searches()
        self._update_searches(log, new_saved_searches)
        all_success = True

        update_status(log)  # update transactional state

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

        sent_events = saved_search.last_observed_telemetry
        saved_search.last_observed_telemetry = set()

        try:
            responses = self.splunk_client.saved_search_results(search_id, saved_search)

            for response in responses:
                for message in response['messages']:
                    if message['type'] != "FATAL" and message['type'] != "INFO":
                        log.info(
                            "Received unhandled message for saved search %s, got: %s" % (saved_search.name, message))

                count += len(response["results"])
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
            if not self.instance_config.ignore_saved_search_errors:
                log.error("Received Check exception while processing saved search " + saved_search.name)
                raise e
            log.warning(
                "Check exception occured %s while processing saved search name %s" % (str(e), saved_search.name))
            service_check(AgentCheck.WARNING, tags=self.instance_config.tags, message=str(e))
            return False
        except Exception as e:
            if not self.instance_config.ignore_saved_search_errors:
                log.error("Received an exception while processing saved search " + saved_search.name)
                raise e
            log.warning("Got an error %s while processing saved search name %s" % (str(e), saved_search.name))
            service_check(AgentCheck.WARNING, tags=self.instance_config.tags, message=str(e))
            return False

        return True

    def _dispatch_saved_search(self, log, persisted_state, saved_search):
        """
        Initiate a saved search, returning the search id
        :param instance: Instance of the splunk instance
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


def chunks(list, n):
    """Yield successive n-sized chunks from l."""
    if PY3:
        for i in range(0, len(list), n):
            yield list[i:i + n]
    else:
        for i in xrange(0, len(list), n):  # noqa: F821
            yield list[i:i + n]
