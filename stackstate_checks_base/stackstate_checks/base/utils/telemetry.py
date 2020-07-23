from enum import Enum
import json


class HealthState(Enum):
    """
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
    def contains_key_value(stream_id, name, contains_key, contains_value, found_health_state, missing_health_state):
        """
        """
        return {
            "stream_id": stream_id,
            "name": name,
            "contains_key": contains_key,
            "contains_value": contains_value,
            "found_health_state": found_health_state.name,
            "missing_health_state": missing_health_state.name,
            "is_event_contains_key_value_check": True
        }

    @staticmethod
    def use_tag_as_health(stream_id, name, tag_name):
        """
        """
        return {
            "stream_id": stream_id,
            "name": name,
            "tag_name": tag_name,
            "is_event_tag_as_health_check": True
        }

    @staticmethod
    def service_check_health(stream_id, name):
        """
        """
        return {
            "stream_id": stream_id,
            "name": name,
            "is_service_check_health_check": True
        }

    @staticmethod
    def custom_health_check(name, check_arguments):
        """
        """
        return dict(check_arguments, **{"name": name})


class MetricHealthChecks(object):
    """
    """

    @staticmethod
    def _single_stream_check_base(stream_id, name, deviating_value, critical_value):
        return {
            "stream_id": stream_id,
            "name": name,
            "deviating_value": deviating_value,
            "critical_value": critical_value,
        }

    @staticmethod
    def maximum_average(stream_id, name, deviating_value, critical_value):
        """
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value),
                    **{"is_metric_maximum_average_check": True})

    @staticmethod
    def maximum_percentile(stream_id, name, deviating_value, critical_value):
        """
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value),
                    **{"is_metric_maximum_percentile_check": True})

    @staticmethod
    def maximum_last(stream_id, name, deviating_value, critical_value):
        """
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value),
                    **{"is_metric_maximum_last_check": True})

    @staticmethod
    def maximum_ratio(denominator, numerator, name, deviating_value, critical_value):
        """
        """
        return {
            "is_metric_maximum_ratio_check": True,
            "denominator": denominator,
            "numerator": numerator,
            "name": name,
            "deviating_value": deviating_value,
            "critical_value": critical_value,
        }

    @staticmethod
    def minimum_average(stream_id, name, deviating_value, critical_value):
        """
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value),
                    **{"is_metrics_minimum_average_check": True})

    @staticmethod
    def minimum_last(stream_id, name, deviating_value, critical_value):
        """
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value),
                    **{"is_metrics_minimum_average_check": True})

    @staticmethod
    def minimum_percentile(stream_id, name, deviating_value, critical_value):
        """
        """
        return dict(MetricHealthChecks._single_stream_check_base(stream_id, name, deviating_value, critical_value),
                    **{"is_metric_minimum_percentile_check": True})

    @staticmethod
    def failed_ratio(success, failed, name, deviating_value, critical_value):
        """
        """
        return {
            "is_metrics_failed_ratio_check": True,
            "success": success,
            "failed": failed,
            "name": name,
            "deviating_value": deviating_value,
            "critical_value": critical_value,
        }

    @staticmethod
    def custom_health_check(name, check_arguments):
        """
        """
        return dict(check_arguments, **{"name": name})


class TelemetryStream(object):
    """
    creates a telemetry stream definition for the component that will bind metrics / events in StackState for the
    conditions.
    """
    def __init__(self, name, conditions):
        self.name = name
        self.conditions = conditions
        self.check = None

    def identifier(self):
        return "{}".format(hash(frozenset(json.dumps(self._as_topology(), sort_keys=True))))

    def to_payload(self):
        return dict(self._as_topology(), **{"identifier": self.identifier()})

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
    args: `name, metricField, conditions, unit_of_measure, aggregation, priority`
    `name` The name for the stream in StackState
    `metricField` the name of the event to select
    `conditions` is a dictionary of key -> value arguments that are used to filter the event values for the stream.
    """
    pass
