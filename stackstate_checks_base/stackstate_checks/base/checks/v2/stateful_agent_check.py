from typing import Optional

from .base import AgentCheckV2
from .mixins import StatefulMixin
from .types import InstanceType, StateType, CheckResponse


class StatefulAgentCheck(StatefulMixin, AgentCheckV2):
    """
    StatefulAgentCheck is an alias for AgentCheckV2 with StatefulMixin already mixed in. This is the preferred
    class to extend when writing a check that needs stateful behaviour.
    """

    def check(self, instance):  # type: (InstanceType) -> CheckResponse
        """
        Check implements the AgentCheckV2 check function and automagically handles the stateful operations for this
        check run.
        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @return: Optional[CheckError] if an error occurs during the check the exception / error is returned.
        """

        # get current state > call the check > set the state
        current_state = self.get_state()
        check_response = self.stateful_check(instance, current_state)
        self.set_state(check_response.persistent_state)

        return check_response

    def stateful_check(self, instance, persistent_state):
        # type: (InstanceType, StateType) -> CheckResponse
        """
        This method should be implemented for a Stateful Check. It's called from run method.
        All Errors raised from stateful_check will be caught and converted to service_call in the run method.

        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @param persistent_state: StateType the current persistent state for this check + persistence key.
        @return: tuple of state: StateType and an optional check error: Optional[CheckError] that is set as the new
        state.
        """
        raise NotImplementedError
