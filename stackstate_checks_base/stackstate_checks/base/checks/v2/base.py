import copy
import json
import traceback

from typing import Any, Optional

from .instance_type import InstanceType
from .mixins import HealthMixin
from .check_error import CheckError
from ..base import AgentCheck
from ...utils.common import to_string

try:
    import topology

    using_stub_topology = False
except ImportError:
    from stackstate_checks.base.stubs import topology

    using_stub_topology = True

DEFAULT_RESULT = to_string(b'')


class AgentCheckV2Base(AgentCheck):
    """
    AgentCheckV2Base
    """

    def check(self, instance):  # type: (InstanceType) -> Optional[CheckError]
        """
        @param instance: InstanceType represents the instance type for this agent check
        @return: Optional[CheckError] returns an optional CheckError
        """
        raise NotImplementedError

    def setup(self):  # type: () -> None
        """

        @return:
        """

        pass

    def on_success(self):
        # type: () -> None
        pass

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
        super(AgentCheckV2Base, self).__init__(*args, **kwargs)

    def run(self):
        # type: () -> str
        """
        Runs stateful check.
        """
        instance_tags = None
        try:
            # start auto snapshot if with_snapshots is set to True
            if self._get_instance_key().with_snapshots:
                topology.submit_start_snapshot(self, self.check_id, self._get_instance_key_dict())

            # create integration instance components for monitoring purposes
            self.create_integration_instance()

            # Call setup on the mixins
            self.setup()

            # create a copy of the check instance, get state if any and add it to the instance object for the check
            instance = self.instances[0]
            check_instance = copy.deepcopy(instance)
            check_instance = self._get_instance_schema(check_instance)
            instance_tags = check_instance.get("instance_tags", [])

            check_result = self.check(check_instance)

            if check_result:
                raise check_result

            # stop auto snapshot if with_snapshots is set to True
            if self._get_instance_key().with_snapshots:
                topology.submit_stop_snapshot(self, self.check_id, self._get_instance_key_dict())

            result = DEFAULT_RESULT
            msg = "{} check was processed successfully".format(self.name)
            self.service_check(self.name, AgentCheck.OK, tags=instance_tags, message=msg)
        except Exception as e:
            result = json.dumps([
                {
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                }
            ])
            self.log.exception(str(e))
            self.service_check(self.name, AgentCheck.CRITICAL, tags=instance_tags, message=str(e))
        finally:
            if self.metric_limiter:
                self.metric_limiter.reset()

        return result


class AgentCheckV2(HealthMixin, AgentCheckV2Base):

    def check(self, instance):
        # type: (InstanceType) -> Optional[CheckError]
        raise NotImplementedError
