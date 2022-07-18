import urllib
from typing import Any, Dict, Optional, TypeVar
from enum import Enum
from schematics import Model
from schematics.exceptions import ValidationError
from schematics.transforms import import_converter
from schematics.types import IntType, ModelType, BaseType
from .schemas import StrictStringType, ClassType
from six import PY3, string_types

try:
    import health

    using_stub_health = False
except ImportError:
    from ..stubs import health

    using_stub_health = True

_InstanceType = TypeVar('_InstanceType', Model, Dict[str, Any])


class Health(Enum):
    CLEAR = "CLEAR"
    DEVIATING = "DEVIATING"
    CRITICAL = "CRITICAL"


class HealthType(BaseType):
    def __init__(self, **kwargs):
        super(HealthType, self).__init__(**kwargs)

    def convert(self, value, context=None):
        if isinstance(value, Health):
            return value

        # check if this is a string or bytes which is converted to string in super.convert()
        if not isinstance(value, string_types):
            raise ValidationError('Value must be a string or Health')

        if value.upper() in Health._member_names_:
            return Health[value.upper()]

        raise ValidationError('Health value must be clear, deviating or critical')


class HealthStreamUrn(object):
    """
    Represents the urn of a health stream
    """
    def __init__(self, source, stream_id):
        self.source = import_converter(StrictStringType(required=True), source, None)
        self.stream_id = import_converter(StrictStringType(required=True), stream_id, None)

    def urn_string(self):
        if PY3:
            encoded_source = urllib.parse.quote(self.source, safe='')
            encoded_stream = urllib.parse.quote(self.stream_id, safe='')
        else:
            encoded_source = urllib.quote(self.source)
            encoded_stream = urllib.quote(self.stream_id)
        return "urn:health:%s:%s" % (encoded_source, encoded_stream)


class HealthStream(object):
    """
    Data structure for defining a health stream, a unique identifier for a health stream source.

    This is not meant to be used in checks.
    """

    def __init__(self, urn, sub_stream="", repeat_interval_seconds=None, expiry_seconds=None):
        """
        :param urn: the urn of the health stream. needs to be of the type HealthStreamUrn
        :param sub_stream: (optional) an identifier for the sub stream. a sub stream can be used if an individual
                           check instance only synchronizes part of a complete streams' data
        :param repeat_interval_seconds: (optional) the interval in which the data will be repeated.
                                        will default to the check instance collection_interval
        :param expiry_seconds: (optional) the time after which health check states will be expired.
                               Providing 0 will disable expiry, which can only be done when no substream is specified
                               Expiry is mandatory when specifying a substream,
                               by default will be four times the repeat_interval_seconds
        """
        self.urn = import_converter(ClassType(HealthStreamUrn, required=True), urn, None)
        self.sub_stream = import_converter(StrictStringType(required=True), sub_stream, None)
        self.repeat_interval_seconds = import_converter(IntType(), repeat_interval_seconds, None)
        self.expiry_seconds = import_converter(IntType(), expiry_seconds, None)
        if sub_stream != "" and expiry_seconds == 0:
            raise ValueError("Expiry cannot be disabled if a substream is specified")

    def to_dict(self):
        return {"urn": self.urn.urn_string(), "sub_stream": self.sub_stream}


class HealthCheckData(Model):
    checkStateId = StrictStringType(required=True)
    name = StrictStringType(required=True)
    health = HealthType(required=True)
    topologyElementIdentifier = StrictStringType(required=True)
    message = StrictStringType(required=False)


class HealthApiCommon(object):
    def __init__(self, *args, **kwargs):
        """
        HealthApiCommon initializes the Common Health API Functionality and passes the args and kwargs to the super init

        @param args: *Any
        @param kwargs: **Any
        """
        super(HealthApiCommon, self).__init__(*args, **kwargs)

        self.health = None  # type: Optional[HealthApi]

    def get_health_stream(self, instance):
        # type: (_InstanceType) -> Optional[HealthStream]
        """
        Integration checks can override this if they want to be producing a health stream. Defining the will
        enable self.health() calls

        :return: a class extending HealthStream
        """
        return None

    def _init_health_api(self):
        # type: () -> None
        if self.health is not None:
            return None

        stream_spec = self.get_health_stream(self._get_instance_schema(self.instance))
        if stream_spec:
            # collection_interval should always be set by the agent
            collection_interval = self.instance['collection_interval']
            repeat_interval_seconds = stream_spec.repeat_interval_seconds or collection_interval
            expiry_seconds = stream_spec.expiry_seconds
            # Only apply a default expiration when we are using substreams
            if expiry_seconds is None:
                if stream_spec.sub_stream != "":
                    expiry_seconds = repeat_interval_seconds * 4
                else:
                    # Explicitly disable expiry setting it to 0
                    expiry_seconds = 0
            self.health = HealthApi(self, stream_spec, expiry_seconds, repeat_interval_seconds)


class HealthApi(object):
    """
    Api for health state synchronization
    """
    def __init__(self, check, stream, expiry_seconds, repeat_interval_seconds):
        self.check = check
        self.stream = stream
        self.expiry_seconds = expiry_seconds
        self.repeat_interval_seconds = repeat_interval_seconds

    def start_snapshot(self):
        health.submit_health_start_snapshot(self.check,
                                            self.check.check_id,
                                            self.stream.to_dict(),
                                            self.expiry_seconds,
                                            self.repeat_interval_seconds)

    def stop_snapshot(self):
        health.submit_health_stop_snapshot(self.check, self.check.check_id, self.stream.to_dict())

    def check_state(self, check_state_id, name, health_value, topology_element_identifier, message=None):
        """
        Send check data for health synchronization

        :param check_state_id: unique identifier for the check state within the (sub)stream
        :param name: Name of the check
        :param health_value: health value, should be of type Health()
        :param topology_element_identifier: string value, represents a component/relation the check state will bind to
        :param message: optional message with the check state
        """
        check_data = {
            'checkStateId': check_state_id,
            'name': name,
            'topologyElementIdentifier': topology_element_identifier
        }

        if isinstance(health_value, Health):
            check_data['health'] = health_value.value
        else:
            raise ValueError("Health value is not of type Health")

        if message:
            check_data['message'] = message

        # Validate the data
        HealthCheckData(check_data).validate()

        health.submit_health_check_data(self.check, self.check.check_id, self.stream.to_dict(), check_data)
