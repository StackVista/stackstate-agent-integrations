from typing import Any, Optional
from .mixins import CheckMixin
from ..instance_type import InstanceType
from ....utils.health_api import HealthApi, HealthStream


class HealthMixin(CheckMixin):
    """

    """

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        """
        - **name** (_str_) - the name of the check
        - **init_config** (_dict_) - the `init_config` section of the configuration.
        - **agentConfig** (_dict_) - deprecated
        - **instance** (_List[dict]_) - a one-element list containing the instance options from the
                configuration file (a list is used to keep backward compatibility with
                older versions of the Agent).
        """
        super(HealthMixin, self).__init__(*args, **kwargs)
        # self._get_instance_schema =
        # self.instance =
        self.health = None  # type: Optional[HealthApi]

    def get_health_stream(self, instance):  # type: (InstanceType) -> Optional[HealthStream]
        """
        Integration checks can override this if they want to be producing a health stream. Defining this will
        enable self.health() calls

        @param instance:
        @return: a class extending HealthStream
        """
        return None

    def setup(self):  # type: () -> None
        """

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
