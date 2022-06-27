from typing import Any, Optional
from .mixins import CheckMixin
from ..types import InstanceType
from ....utils.health_api import HealthApi, HealthStream


class HealthMixin(CheckMixin):
    """
    HealthMixin extends the Agent Check base with the Health API allowing Agent Checks to start submitting health data.
    """

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        """
        HealthMixin initializes the Agent Check V2 base class and passes the args and kwargs to the super init, and
        declares the health variable which is an Optional[HealthApi] defaulted to None. It is initialized in setup.

        @param args: *Any
        @param kwargs: **Any
        """
        super(HealthMixin, self).__init__(*args, **kwargs)
        # self._get_instance_schema =
        # self.instance =
        self.health = None  # type: Optional[HealthApi]

    def get_health_stream(self, instance):  # type: (InstanceType) -> Optional[HealthStream]
        """
        Integration checks can override this if they want to be producing a health stream. Defining this will
        enable self.health() calls.

        @param instance:
        @return: a class extending HealthStream
        """
        return None

    def setup(self):  # type: () -> None
        """
        setup is used to initialize the HealthApi and set the health variable to be used in checks.

        @return: None
        """

        if self.health is not None:
            return None

        stream_spec = self.get_health_stream(self._get_instance_schema(self.instance))
        if stream_spec:
            # collection_interval should always be set by the agent
            collection_interval = self.instance['collection_interval']
            repeat_interval_seconds = stream_spec.repeat_interval_seconds or collection_interval
            expiry_seconds = stream_spec.expiry_seconds
            # Only apply a default expiration when we are using sub_streams
            if expiry_seconds is None:
                if stream_spec.sub_stream != "":
                    expiry_seconds = repeat_interval_seconds * 4
                else:
                    # Explicitly disable expiry setting it to 0
                    expiry_seconds = 0
            self.health = HealthApi(self, stream_spec, expiry_seconds, repeat_interval_seconds)
