import sys
import time
import traceback

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

    def __init__(self, name, init_config, agent_config, instances=None):
        super(SplunkTelemetryBase, self).__init__(name, init_config, agent_config, instances)
        # Data to keep over check runs
        self.splunk_telemetry_instance = None

        # Data to keep over check runs
        self.instance_data = None
        self.continue_after_commit = True

    def get_instance_key(self, instance):
        return TopologyInstance(SplunkTelemetryInstance.INSTANCE_TYPE, instance["url"])

    def get_instance(self, instance, current_time):
        raise NotImplementedError

    def transactional_check(self, instance, transactional_state, persistent_state):

        current_time = self._current_time_seconds()
        if not self.splunk_telemetry_instance:
            self.splunk_telemetry_instance = self.get_instance(instance, current_time)

        if not self.splunk_telemetry_instance.initial_time_done(current_time):
            self.log.debug("Skipping splunk metric/event instance %s, waiting for initial time"
                           " to expire" % instance.get("url"))
            return CheckResponse(transactional_state=transactional_state,
                                 persistent_state=persistent_state,
                                 check_error=None)

        splunk_persistent_state = SplunkPersistentState(persistent_state)

        try:
            self.splunk_telemetry_instance.splunk_client.auth_session(splunk_persistent_state)

            def _service_check(status, tags=None, hostname=None, message=None):
                self.service_check(self.SERVICE_CHECK_NAME, status, tags, hostname, message)

            def _process_data(saved_search, response, sent_already):
                fail_count = 0
                for data_point in self._extract_telemetry(saved_search, self.splunk_telemetry_instance, response,
                                                          sent_already):
                    if data_point is None:
                        fail_count += 1
                    else:
                        self._apply(**data_point)
                return fail_count

            def _update_status():
                self.log.debug("Called SplunkTelemetryBase._update_status")
                self.splunk_telemetry_instance.update_status(current_time=current_time, data=transactional_state)

            self.splunk_telemetry_instance.saved_searches.run_saved_searches(_process_data, _service_check, self.log,
                                                                             splunk_persistent_state,
                                                                             _update_status)

            # Continue Process
            transactional_state, continue_after_commit = self.splunk_telemetry_instance.get_status()

            self.continue_after_commit = continue_after_commit

            # If no service checks were produced, everything is ok
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK)
        except TokenExpiredException as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL,
                               tags=self.splunk_telemetry_instance.instance_config.tags,
                               message=str(e.message))
            self.log.exception("Splunk metric exception: %s" % str(e))
        except Exception as e:
            print(traceback.print_exc())
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL,
                               tags=self.splunk_telemetry_instance.instance_config.tags,
                               message=str(e))
            self.log.exception("Splunk metric exception: %s" % str(e))
            if not self.splunk_telemetry_instance.instance_config.ignore_saved_search_errors:
                return CheckResponse(transactional_state=transactional_state,
                                     persistent_state=splunk_persistent_state.state,
                                     check_error=CheckException(
                                         "Splunk metric failed with message: %s" % e,
                                         None,
                                         sys.exc_info()[2]
                                     ))

        return CheckResponse(transactional_state=transactional_state,
                             persistent_state=splunk_persistent_state.state,
                             check_error=None)

    def _extract_telemetry(self, saved_search, instance, result, sent_already):
        for data in result.get("results", []):
            # We need a unique identifier for splunk events, according to
            # https://answers.splunk.com/answers/334613/is-there-a-unique-event-id-for-each-event-in-the-i.html
            # this can be (server, index, _cd)

            try:
                if not saved_search.unique_key_fields:  # empty list, whole record
                    current_id = tuple(data)
                else:
                    for field in saved_search.unique_key_fields:
                        if field not in data.keys():
                            self.log.warning("Field %s not found in data" % field)
                            continue
                        else:
                            current_id = data[field]

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
                    for key, value in self._filter_fields(data).items()
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
            for key, value in data.items()
            if self._include_as_tag(key)
        }

    def _current_time_seconds(self):
        """ This method is mocked for testing. Do not change its behavior """
        return int(round(time.time()))

    def _include_as_tag(self, key):
        return not key.startswith('_') and key not in self.basic_default_fields.union(self.date_default_fields)

    def _apply(self, **kwargs):
        """ How the telemetry info should be sent by the check, e.g., as event, guage, etc. """
        raise NotImplementedError
