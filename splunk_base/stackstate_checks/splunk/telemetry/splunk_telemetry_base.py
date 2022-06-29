import sys
import time

from stackstate_checks.base import AgentCheck, TopologyInstance
from stackstate_checks.base.checks import TransactionalAgentCheck, CheckResponse
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import TokenExpiredException
from stackstate_checks.splunk.config import SplunkPersistentState
from stackstate_checks.splunk.config.splunk_instance_config import time_to_seconds, take_required_field
from stackstate_checks.splunk.telemetry.splunk_telemetry import SplunkTelemetryInstance


class SplunkTelemetryBase(TransactionalAgentCheck):
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
        return TopologyInstance(SplunkTelemetryInstance.INSTANCE_TYPE, instance["url"])

    def get_instance(self, instance, current_time):
        raise NotImplementedError

    def transactional_check(self, instance, transactional_state, persistent_state):

        current_time = self._current_time_seconds()
        url = instance["url"]
        if url not in self.instance_data:
            self.instance_data[url] = self.get_instance(instance, current_time)

        pstate = SplunkPersistentState(persistent_state)

        instance = self.instance_data

        try:
            instance.splunk_client.auth_session(pstate)

            def _service_check(status, tags=None, hostname=None, message=None):
                self.service_check(self.SERVICE_CHECK_NAME, status, tags, hostname, message)

            def _process_data(saved_search, response, sent_already):
                return self._extract_telemetry(saved_search, instance, response, sent_already)

            def _update_status():
                self.log.debug("Called SplunkTelemetryBase._update_status")
                instance.update_status(current_time=current_time, data=transactional_state)

            instance.saved_searches.run_saved_searches(_process_data, _service_check, self.log, pstate, _update_status)


            # If no service checks were produced, everything is ok
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK)

            return CheckResponse(transactional_state=transactional_state,
                                 persistent_state=pstate.state,
                                 check_error=None)

        except TokenExpiredException as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.instance_config.tags,
                               message=str(e.message))
            self.log.exception("Splunk metric exception: %s" % str(e))
            return CheckResponse(transactional_state=transactional_state,
                                 persistent_state=pstate.state,
                                 check_error=e)
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.instance_config.tags,
                               message=str(e))
            self.log.exception("Splunk metric exception: %s" % str(e))
            if not instance.instance_config.ignore_saved_search_errors:
                raise CheckException("Splunk metric failed with message: %s" % e, None, sys.exc_info()[2])
            return CheckResponse(transactional_state=transactional_state,
                                 persistent_state=pstate.state,
                                 check_error=e)

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
                    for key, value in self._filter_fields(data).iteritems()  # TODO what to do with `iteritems`?
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
            for key, value in data.iteritems()  # TODO what to do with `iteritems`?
            if self._include_as_tag(key)
        }

    def _current_time_seconds(self):
        """ This method is mocked for testing. Do not change its behavior """
        return int(round(time.time()))

    def _include_as_tag(self, key):
        return not key.startswith('_') and key not in self.basic_default_fields.union(self.date_default_fields)

