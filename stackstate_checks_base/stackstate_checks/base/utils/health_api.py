import urllib
from typing import Any, Dict, Optional, TypeVar
from enum import Enum
from pydantic import ValidationError, Field, model_validator
from six import PY3
from .validations_utils import CheckBaseModel

try:
    import health

    using_stub_health = False
except ImportError:
    from ..stubs import health

    using_stub_health = True

_InstanceType = TypeVar('_InstanceType', CheckBaseModel, Dict[str, Any])


class Health(str, Enum):
    CLEAR = "CLEAR"
    DEVIATING = "DEVIATING"
    CRITICAL = "CRITICAL"

    # Make case-insensitive
    @classmethod
    def _missing_(cls, value):
        value = value.lower()
        for member in cls:
            if member.lower() == value:
                return member
        return None


class HealthType(object):
    def __init__(self, **kwargs):
        super(HealthType, self).__init__(**kwargs)

    def convert(self, value):
        if isinstance(value, Health):
            return value

        try:
            return Health(value)
        except ValueError as e:
            raise ValidationError("Error parsing health") from e


class HealthStreamUrn(CheckBaseModel):
    """
    Represents the urn of a health stream
    """

    source: str
    stream_id: str

    def __init__(self, source, stream_id):
        super(HealthStreamUrn, self).__init__(source=source, stream_id=stream_id)

    def urn_string(self):
        if PY3:
            encoded_source = urllib.parse.quote(self.source, safe='')
            encoded_stream = urllib.parse.quote(self.stream_id, safe='')
        else:
            encoded_source = urllib.quote(self.source)
            encoded_stream = urllib.quote(self.stream_id)
        return "urn:health:%s:%s" % (encoded_source, encoded_stream)


class HealthStream(CheckBaseModel):
    """
    Data structure for defining a health stream, a unique identifier for a health stream source.

    This is not meant to be used in checks.
    """
    urn: HealthStreamUrn
    sub_stream: str = Field(default="")
    repeat_interval_seconds: Optional[int] = None
    expiry_seconds: Optional[int] = None

    def __init__(self, urn, sub_stream="", repeat_interval_seconds=None, expiry_seconds=None):
        super(HealthStream, self).__init__(
            urn=urn, sub_stream=sub_stream, repeat_interval_seconds=repeat_interval_seconds,
            expiry_seconds=expiry_seconds)

    @model_validator(mode='after')
    def check_sub_stream_expiry(self):
        if self.sub_stream != "" and self.expiry_seconds == 0:
            raise ValueError("Expiry cannot be disabled if a substream is specified")
        return self

    def to_dict(self):
        return {"urn": self.urn.urn_string(), "sub_stream": self.sub_stream}


class HealthCheckData(CheckBaseModel):
    checkStateId: str
    name: str
    health: Health
    topologyElementIdentifier: str
    message: Optional[str] = None


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
            'topologyElementIdentifier': topology_element_identifier,
            'health': health_value
        }

        if message:
            check_data['message'] = message

        # Validate the data
        HealthCheckData(**check_data)

        # Turn enum into string for passing to golang
        check_data['health'] = check_data['health'].value

        health.submit_health_check_data(self.check, self.check.check_id, self.stream.to_dict(), check_data)
