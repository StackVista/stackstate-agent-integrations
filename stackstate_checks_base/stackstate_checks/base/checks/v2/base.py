import copy
import json
import traceback

from typing import Any, Optional

from .types import InstanceType, CheckResponse
from .mixins import HealthMixin
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
    AgentCheckV2Base is the base class for V2 of Agent Checks. The key difference being that for V2 checks the check
    method requires an Optional[CheckError] as a return value and allows the check base to act accordingly given the
    result of the check run.
    """

    def check(self, instance):  # type: (InstanceType) -> CheckResponse
        """
        check is the entry point for Agent Checks. This must be overridden.

        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @return: Optional[CheckError] if an error occurs during the check the exception / error is returned.
        """
        raise NotImplementedError

    def setup(self):  # type: () -> None
        """
        setup is an abstract method that can be overridden by check mixins to "setup" the mixin and make it ready for
        the check runs.
        @return: None
        """
        pass

    def on_success(self):  # type: () -> None
        """
        on_success is an abstract method that can be overridden by check mixins to perform some actions upon a
        successful check run.
        @return: None
        """
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

    def run(self):  # type: () -> str
        """
        run is the entrypoint for the StackState Agent when scheduling and running agent checks.

        @return: string representing the result of the check run. If the check was successful run returns an empty
        string.
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

            if check_result and check_result.check_error:
                raise check_result.check_error

            # Call on_success on the mixins
            self.on_success()

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
    """
    AgentCheckV2 is the AgentCheck base class for all V2 Agent Checks. Checks that extend this must override the check
    method.
    """

    def check(self, instance):  # type: (InstanceType) -> CheckResponse
        """
        check is the entry point for V2 Agent Checks. This must be overridden.

        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @return: Optional[CheckError] if an error occurs during the check the exception / error is returned.
        """
        raise NotImplementedError
