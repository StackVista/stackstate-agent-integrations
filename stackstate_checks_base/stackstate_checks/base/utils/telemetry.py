# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from six import iteritems
from enum import Enum
import uuid
from schematics import Model
from schematics.types import URLType, ModelType, ListType, IntType, BaseType
from .schemas import StrictStringType


class HealthState(Enum):
    """
    The different HealthStates supported in StackState
    """
    UNKNOWN = "UNKNOWN"
    CLEAR = "CLEAR"
    DISABLED = "DISABLED"
    DEVIATING = "DEVIATING"
    FLAPPING = "FLAPPING"
    CRITICAL = "CRITICAL"


class EventHealthChecks(object):
    """
    """

    @staticmethod
    def _is_valid_health_state(health_state):
        return HealthState[health_state]

    @staticmethod
    def contains_key_value(stream_id, name, contains_key, contains_value, found_health_state, missing_health_state,
                           description=None, remediation_hint=None):
        """
        Check that the last event contains (at the top-level), the specified value for a key.
        Returns 'found_health_state' value when the state is contained and 'missing_health_state' when it is not
        contained.
        args: `stream_id, name, contains_key, contains_value, found_health_state, missing_health_state, description,
               remediation_hint`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `contains_key` the key that should be contained in the event
        `contains_value` the value that should be contained in the event
        `found_health_state` the health state to return when this tag and value is found
        `missing_health_state` the health state to return when the tag/value is not found
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        """
        check = {
            "stream_id": stream_id,
            "name": name,
            "contains_key": contains_key,
            "contains_value": contains_value,
            "found_health_state": EventHealthChecks._is_valid_health_state(found_health_state).name,
            "missing_health_state": EventHealthChecks._is_valid_health_state(missing_health_state).name,
            "is_event_contains_key_value_check": True
        }

        if description:
            check["description"] = description

        if remediation_hint:
            check["remediation_hint"] = remediation_hint

        return check

    @staticmethod
    def use_tag_as_health(stream_id, name, tag_name, description=None, remediation_hint=None):
        """
        Check that returns the value of a tag in the event as the health state.
        args: `stream_id, name, tag_name, description, remediation_hint`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `tag_name` the key of the tag that should be be used as the health state
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        """
        check = {
            "stream_id": stream_id,
            "name": name,
            "tag_name": tag_name,
            "is_event_tag_as_health_check": True
        }

        if description:
            check["description"] = description

        if remediation_hint:
            check["remediation_hint"] = remediation_hint

        return check

    @staticmethod
    def custom_health_check(name, check_arguments):
        """
        This method provides the functionality to send in a custom event health check.
        args: `name, check_arguments`
        `name` the name this check will have in StackState
        `check_arguments` the check arguments
        """
        return dict(check_arguments, **{"name": name})


class MetricHealthChecks(object):
    """
    """

    @staticmethod
    def _single_stream_check_base(stream_id, name, deviating_value, critical_value, description, remediation_hint,
                                  max_window):
        check = {
            "stream_id": stream_id,
            "name": name,
            "deviating_value": deviating_value,
            "critical_value": critical_value,
            "max_window": max_window if max_window is not None else 300000,
        }

        if description:
            check["description"] = description

        if remediation_hint:
            check["remediation_hint"] = remediation_hint

        return check

    @staticmethod
    def maximum_average(stream_id, name, deviating_value, critical_value, description=None, remediation_hint=None,
                        max_window=None):
        """
        Calculate the health state by comparing the average of all metric points in the time window against the
        configured maximum values.
        args: `stream_id, name, deviating_value, critical_value, description, remediation_hint, max_window`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `deviating_value` the threshold at which point this check will return a deviating health state
        `critical_value` the threshold at which point this check will return a critical health state
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        `max_window` the max window size for the metrics
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value,
                                                                 description, remediation_hint, max_window),
                    **{"is_metric_maximum_average_check": True})

    @staticmethod
    def maximum_last(stream_id, name, deviating_value, critical_value, description=None, remediation_hint=None,
                     max_window=None):
        """
        Calculate the health state only by comparing the last value in the time window against the configured maximum
        values.
        args: `stream_id, name, deviating_value, critical_value, description, remediation_hint, max_window`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `deviating_value` the threshold at which point this check will return a deviating health state
        `critical_value` the threshold at which point this check will return a critical health state
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        `max_window` the max window size for the metrics
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value,
                                                                 description, remediation_hint, max_window),
                    **{"is_metric_maximum_last_check": True})

    @staticmethod
    def maximum_percentile(stream_id, name, deviating_value, critical_value, percentile, description=None,
                           remediation_hint=None, max_window=None):
        """
        Calculate the health state by comparing the specified percentile of all metric points in the time window against
        the configured maximum values. For the median specify 50 for the percentile. The percentile parameter must be a
        value > 0 and <= 100.
        args: `stream_id, name, deviating_value, critical_value, percentile, description, remediation_hint, max_window`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `deviating_value` the threshold at which point this check will return a deviating health state
        `critical_value` the threshold at which point this check will return a critical health state
        `percentile` the percentile value to use for the calculation
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        `max_window` the max window size for the metrics
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value,
                                                                 description, remediation_hint, max_window),
                    **{"percentile": percentile, "is_metric_maximum_percentile_check": True})

    @staticmethod
    def maximum_ratio(denominator_stream_id, numerator_stream_id, name, deviating_value, critical_value,
                      description=None, remediation_hint=None, max_window=None):
        """
        Calculates the ratio between the values of two streams and compares it against the critical and deviating value.
        If the ratio is larger than the specified critical or deviating value, the corresponding health state is
        returned.
        args: `denominator_stream_id, numerator_stream_id, name, deviating_value, critical_value, description,
        remediation_hint, max_window`
        `denominator_stream_id` the identifier of the denominator stream this check should run on
        `numerator_stream_id` the identifier of the numerator stream this check should run on
        `name` the name this check will have in StackState
        `deviating_value` the threshold at which point this check will return a deviating health state
        `critical_value` the threshold at which point this check will return a critical health state
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        `max_window` the max window size for the metrics
        """
        check = {
            "is_metric_maximum_ratio_check": True,
            "denominator_stream_id": denominator_stream_id,
            "numerator_stream_id": numerator_stream_id,
            "name": name,
            "deviating_value": deviating_value,
            "critical_value": critical_value,
            "max_window": max_window if max_window is not None else 300000,
        }

        if description:
            check["description"] = description

        if remediation_hint:
            check["remediation_hint"] = remediation_hint

        return check

    @staticmethod
    def minimum_average(stream_id, name, deviating_value, critical_value, description=None, remediation_hint=None,
                        max_window=None):
        """
        Calculate the health state by comparing the average of all metric points in the time window against the
        configured minimum values.
        args: `stream_id, name, deviating_value, critical_value, description, remediation_hint, max_window`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `deviating_value` the threshold at which point this check will return a deviating health state
        `critical_value` the threshold at which point this check will return a critical health state
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        `max_window` the max window size for the metrics
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value,
                                                                 description, remediation_hint, max_window),
                    **{"is_metric_minimum_average_check": True})

    @staticmethod
    def minimum_last(stream_id, name, deviating_value, critical_value, description=None, remediation_hint=None,
                     max_window=None):
        """
        Calculate the health state only by comparing the last value in the time window against the configured minimum
        values.
        args: `stream_id, name, deviating_value, critical_value, description, remediation_hint, max_window`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `deviating_value` the threshold at which point this check will return a deviating health state
        `critical_value` the threshold at which point this check will return a critical health state
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        `max_window` the max window size for the metrics
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value,
                                                                 description, remediation_hint, max_window),
                    **{"is_metric_minimum_last_check": True})

    @staticmethod
    def minimum_percentile(stream_id, name, deviating_value, critical_value, percentile, description=None,
                           remediation_hint=None, max_window=None):
        """
        Calculate the health state by comparing the specified percentile of all metric points in the time window against
        the configured minimum values. For the median specify 50 for the percentile. The percentile must be a
        value > 0 and <= 100.
        args: `stream_id, name, deviating_value, critical_value, percentile, description, remediation_hint, max_window`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `deviating_value` the threshold at which point this check will return a deviating health state
        `critical_value` the threshold at which point this check will return a critical health state
        `percentile` the percentile value to use for the calculation
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        `max_window` the max window size for the metrics
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value,
                                                                 description, remediation_hint, max_window),
                    **{"percentile": percentile, "is_metric_minimum_percentile_check": True})

    @staticmethod
    def failed_ratio(success_stream_id, failed_stream_id, name, deviating_value, critical_value,
                     description=None, remediation_hint=None, max_window=None):
        """
        Calculate the ratio between the last values of two streams (one is the normal metric stream and one is the
        failed metric stream). This ratio is compared against the deviating or critical value.
        args: `success_stream_id, failed_stream_id, name, deviating_value, critical_value, description,
               remediation_hint, max_window`
        `success_stream_id` the identifier of the success stream this check should run on
        `failed_stream_id` the identifier of the failures stream this check should run on
        `name` the name this check will have in StackState
        `deviating_value` the threshold at which point this check will return a deviating health state
        `critical_value` the threshold at which point this check will return a critical health state
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        `max_window` the max window size for the metrics
        """
        check = {
            "is_metric_failed_ratio_check": True,
            "denominator_stream_id": success_stream_id,
            "numerator_stream_id": failed_stream_id,
            "name": name,
            "deviating_value": deviating_value,
            "critical_value": critical_value,
            "max_window": max_window if max_window is not None else 300000,
        }

        if description:
            check["description"] = description

        if remediation_hint:
            check["remediation_hint"] = remediation_hint

        return check

    @staticmethod
    def custom_health_check(name, check_arguments):
        """
        This method provides the functionality to send in a custom metric health check.
        args: `name, check_arguments`
        `name` the name this check will have in StackState
        `check_arguments` the check arguments
        """
        return dict(check_arguments, **{"name": name})


class ServiceCheckHealthChecks(object):
    @staticmethod
    def service_check_health(stream_id, name, description=None, remediation_hint=None):
        """
        Check that returns the service check status as a health status in StackState
        args: `stream_id, name, description, remediation_hint`
        `stream_id` the identifier of the stream this check should run on
        `name` the name this check will have in StackState
        `description` the description for this check in StackState
        `remediation_hint` the remediation hint to display when this check return a critical health state
        """
        check = {
            "stream_id": stream_id,
            "name": name,
            "is_service_check_health_check": True
        }

        if description:
            check["description"] = description

        if remediation_hint:
            check["remediation_hint"] = remediation_hint

        return check


class TelemetryStream(object):
    """
    creates a telemetry stream definition for the component that will bind metrics / events in StackState for the
    conditions.
    """
    def __init__(self, name, conditions):
        self.name = name
        # map conditions into the format the backend expects
        _mapped_conditions = []
        for key, value in iteritems(conditions):
            kv = {"key": key, "value": value}
            _mapped_conditions.append(kv)

        self.conditions = sorted(_mapped_conditions, key=lambda c: c['key'])
        self.stream_id = None
        self.identifier = "{}".format(uuid.uuid4())

    def to_payload(self):
        if self.stream_id:
            return dict(self._as_topology(), **{"stream_id": self.stream_id})
        else:
            return self._as_topology()

    def _as_topology(self):
        return {
            "name": self.name,
            "conditions": self.conditions,
        }


class MetricStream(TelemetryStream):
    acceptable_aggregation_methods = ["EVENT_COUNT", "MAX", "MEAN", "MIN", "SUM", "PERCENTILE_25", "PERCENTILE_50",
                                      "PERCENTILE_75", "PERCENTILE_90", "PERCENTILE_95", "PERCENTILE_98",
                                      "PERCENTILE_99"]
    acceptable_stream_priorities = ["NONE", "LOW", "MEDIUM", "HIGH"]
    """
    creates a metric stream definition for the component that will bind metrics in StackState for the conditions.
    args: `name, metricField, conditions, unit_of_measure, aggregation, priority`
    `name` The name for the stream in StackState
    `metricField` the name of the metric to select
    `conditions` is a dictionary of key -> value arguments that are used to filter the metric values for the stream.
    `unit_of_measure` The unit of measure for the metric points, it gets appended after the stream name:
    Stream Name (unit of measure)
    `aggregation` sets the aggregation function for the metrics in StackState. It can be:  EVENT_COUNT, MAX, MEAN,
    MIN, SUM, PERCENTILE_25, PERCENTILE_50, PERCENTILE_75, PERCENTILE_90, PERCENTILE_95, PERCENTILE_98,
    PERCENTILE_99
    `priority` sets the stream priority in StackState, it can be NONE, LOW, MEDIUM, HIGH.
    HIGH priority streams are used in StackState's anomaly detection.
    """
    def __init__(self, name, metric_field, conditions, unit_of_measure=None, aggregation=None, priority=None):
        TelemetryStream.__init__(self, name, conditions)
        self.metric_field = metric_field
        self.unit_of_measure = unit_of_measure
        if aggregation:
            if aggregation not in MetricStream.acceptable_aggregation_methods:
                raise ValueError("Got unexpected value {} for argument aggregation, expected one of {}"
                                 .format(aggregation, MetricStream.acceptable_aggregation_methods))
            self.aggregation = aggregation

        if priority:
            if priority not in MetricStream.acceptable_stream_priorities:
                raise ValueError("Got unexpected value {} for argument priority, expected one of {}"
                                 .format(priority, MetricStream.acceptable_stream_priorities))

            self.priority = priority

    def _as_topology(self):
        metric_stream = TelemetryStream._as_topology(self)

        metric_stream["metric_field"] = self.metric_field

        if self.unit_of_measure:
            metric_stream["unit_of_measure"] = self.unit_of_measure

        if self.aggregation:
            metric_stream["aggregation"] = self.aggregation

        if self.priority:
            metric_stream["priority"] = self.priority

        return metric_stream


class EventStream(TelemetryStream):
    """
    creates a event stream definition for the component that will bind events in StackState for the conditions.
    args: `name, conditions`
    `name` The name for the stream in StackState
    `conditions` is a dictionary of key -> value arguments that are used to filter the event values for the stream.
    """
    pass


class ServiceCheckStream(TelemetryStream):
    """
    creates a service check stream definition for the component that will bind service checks in StackState for the
    conditions.
    args: `name, conditions`
    `name` The name for the stream in StackState
    `conditions` is a dictionary of key -> value arguments that are used to filter the event values for the stream.
    """
    pass


class SourceLink(Model):
    """
    SourceLink is a external source / event that the event might link to
    args:
    `title` the name of the external source / event
    `url` the url at which more information about this event can be found
    """
    title = StrictStringType(required=True)
    url = URLType(fqdn=False, required=True)


class TopologyEventContext(Model):
    """
    EventContext enriches the event with some more context and allows correlation to topology in StackState
    args:
    `source_identifier` an optional identifier for the event from the source
    `element_identifiers` identifiers of 4T data model in terms of URNs. A stream instance identifier is urn:*.
        (indexed) - (details) *'urn://process/C:/processs/with/a/long/path/which/is/really/long',
        'urn://host/lnx5002345', 80% cases 1, 19% cases 2-5, 0,1-1% cases 100+*
    `source` - Kubernetes, ServiceNow, etc.
    `category` - unique category of the event
    `data` - json blob with any extra properties our stackpack builders want to send
    `source_links`[title: String, url: String] - A list of titles and URLs that the event might link to.
    """
    source_identifier = StrictStringType(required=False)
    element_identifiers = ListType(StrictStringType, required=False)
    source = StrictStringType(required=True)
    category = StrictStringType(required=True)
    data = BaseType(required=False)
    source_links = ListType(ModelType(SourceLink), required=False)

    class Options:
        serialize_when_none = False


class Event(Model):
    """
    Event represents some activity that occurred that is of interest to
    args:
    `msg_title` the title of the event
    `msg_text` the text body of the event
    `timestamp` the epoch timestamp for the event
    `source_type_name` the source type name
    `priority` specifies the priority of the event ("normal" or "low")
    `host` the name of the host
    `tags` a list of tags to associate with this event
    `alert_type` one of ('error', 'warning', 'success', 'info'), defaults to 'info'
    `aggregation_key` a key to use for aggregating events
    `event_type` the event name
    `event_context` enriches the event with some more context and allows correlation to topology in StackState
    """
    msg_title = StrictStringType(required=True)
    msg_text = StrictStringType(required=True)
    timestamp = IntType(required=True)
    event_type = StrictStringType(required=True, deserialize_from=['event_type', 'source_type_name'])
    priority = StrictStringType(required=False, choices=['normal', 'low'])
    host = StrictStringType(required=False)
    tags = ListType(StrictStringType, required=False)
    alert_type = StrictStringType(required=False, choices=['error', 'warning', 'success', 'info'], default="info")
    aggregation_key = StrictStringType(required=False)
    context = ModelType(TopologyEventContext, required=False)

    class Options:
        serialize_when_none = False
