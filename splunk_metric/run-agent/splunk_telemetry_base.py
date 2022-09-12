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
        self.log.debug("Running Force Raw Metrics Input")

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

        self.log.debug("Submitting Transactional State: {}".format(transactional_state))
        self.log.debug("Submitting Persistent State: {}".format(splunk_persistent_state.state))

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


# Agent
# splunk-trace-agent  | 2022-09-08 13:54:27 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionmanager/transaction_manager.go:92 in Start) | Setting state agent_integrations_transactional_check_state for transaction b27435b0-bab6-4505-b60f-83381b44ea56: {"transaction_counter": 1}
# splunk-trace-agent  | 2022-09-08 13:54:27 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionbatcher/transactional_batcher_api.go:252 in SubmitComplete) | Submitting complete for check [agent_v2_integration_transactional_sample:d884b5186b651429]
# splunk-trace-agent  | 2022-09-08 13:54:27 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionmanager/transaction_manager.go:82 in Start) | Committing action 5bb61cbc-744c-43a7-a4c2-6fa7e7dea509 for transaction b27435b0-bab6-4505-b60f-83381b44ea56
# splunk-trace-agent  | 2022-09-08 13:54:27 UTC | CORE | INFO | (pkg/collector/runner/runner.go:328 in work) | Done running check agent_v2_integration_transactional_sample


# Splunk
# splunk-trace-agent  | 2022-09-08 13:57:41 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionmanager/transaction_manager.go:92 in Start) | Setting state splunk_httpslemon-lights-hide-31-201-26-106localt_transactional_check_state for transaction 4f3a043a-2dcb-440e-ab9e-38cff70c7368: {"metrics": 1662645438.0}
# splunk-trace-agent  | 2022-09-08 13:57:41 UTC | CORE | INFO | (pkg/collector/runner/runner.go:328 in work) | Done running check splunk_metric
# splunk-trace-agent  | 2022-09-08 13:57:41 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionbatcher/transactional_batcher_api.go:252 in SubmitComplete) | Submitting complete for check [splunk_metric:dfc4c99c99e25e70]
# splunk-trace-agent  | 2022-09-08 13:57:41 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionmanager/transaction_manager.go:82 in Start) | Committing action bc4880fa-1f0d-4ce6-b65a-4979c6d8e620 for transaction 4f3a043a-2dcb-440e-ab9e-38cff70c7368


# No Data
# splunk-trace-agent  | 2022-09-08 14:06:01 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionmanager/transaction_manager.go:92 in Start) | Setting state splunk_httpslemon-lights-hide-31-201-26-106localt_transactional_check_state for transaction 52ba6739-fd31-44ac-a7ae-cedef6d1faa3: {"metrics": 1662645960}
# splunk-trace-agent  | 2022-09-08 14:06:01 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionmanager/transaction_manager.go:82 in Start) | Committing action 14719f7e-c100-485f-b3d1-ad498bb39aa7 for transaction 52ba6739-fd31-44ac-a7ae-cedef6d1faa3
# splunk-trace-agent  | 2022-09-08 14:06:01 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionmanager/transaction_manager.go:87 in Start) | Acknowledging action 14719f7e-c100-485f-b3d1-ad498bb39aa7 for transaction 52ba6739-fd31-44ac-a7ae-cedef6d1faa3
# splunk-trace-agent  | 2022-09-08 14:06:01 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionmanager/transaction_manager.go:106 in Start) | Completing transaction 52ba6739-fd31-44ac-a7ae-cedef6d1faa3
# splunk-trace-agent  | 2022-09-08 14:06:01 UTC | CORE | DEBUG | (pkg/collector/transactional/transactionbatcher/transactional_batcher_api.go:252 in SubmitComplete) | Submitting complete for check [splunk_metric:dfc4c99c99e25e70]
# splunk-trace-agent  | 2022-09-08 14:06:01 UTC | CORE | DEBUG | (pkg/collector/check/handler/check_handler_transactional.go:201 in handleCurrentTransaction) | Completing transaction: 52ba6739-fd31-44ac-a7ae-cedef6d1faa3 for check splunk_metric:dfc4c99c99e25e70
# splunk-trace-agent  | 2022-09-08 14:06:01 UTC | CORE | DEBUG | (pkg/collector/check/handler/check_handler_transactional.go:204 in handleCurrentTransaction) | Committing state for transaction: 52ba6739-fd31-44ac-a7ae-cedef6d1faa3 for check splunk_metric:dfc4c99c99e25e70: &{splunk_httpslemon-lights-hide-31-201-26-106localt_transactional_check_state {"metrics": 1662645960}}
# splunk-trace-agent  | 2022-09-08 14:06:01 UTC | CORE | DEBUG | (pkg/collector/check/handler/check_handler_transactional.go:214 in handleCurrentTransaction) | Successfully committed state for transaction: 52ba6739-fd31-44ac-a7ae-cedef6d1faa3 for check splunk_metric:dfc4c99c99e25e70: &{splunk_httpslemon-lights-hide-31-201-26-106localt_transactional_check_state {"metrics": 1662645960}}


# Empty
# Submitting Transactional State: {'metrics': 1662727069}
# Submitting Persistent State: {'sid_metrics': u'admin__admin__search__metrics_at_1662727070_55'}

# Working
# Submitting Transactional State: {'metrics': 1662727143}
# Submitting Persistent State: {'sid_metrics': u'admin__admin__search__metrics_at_1662727146_56'}
