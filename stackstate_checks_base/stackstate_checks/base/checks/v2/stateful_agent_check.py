from schematics import Model
from typing import Any, Dict, Optional, Union

from .base import AgentCheckV2
from .check_error import CheckError
from .types import InstanceType, StateType
from .mixins import StatefulMixin


class StatefulAgentCheck(StatefulMixin, AgentCheckV2):
    """
    StatefulAgentCheck is an alias for AgentCheckV2 with StatefulMixin already mixed in. This is the preferred
    class to extend when writing a check that needs stateful behaviour.
    """

    def check(self, instance):  # type: (InstanceType) -> Optional[CheckError]
        """
        Check implements the AgentCheckV2 check function and automagically handles the stateful operations for this
        check run.
        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @return: Optional[CheckError] if an error occurs during the check the exception / error is returned.
        """

        # get current state > call the check > set the state
        current_state = self.get_state()
        new_state, check_error = self.stateful_check(instance, current_state)

        if check_error:
            return check_error

        self.set_state(new_state)

        return

    def stateful_check(self, instance, state):
        # type: (InstanceType, StateType) -> (StateType, Optional[CheckError])
        """
        This method should be implemented for a Stateful Check. It's called from run method.
        All Errors raised from stateful_check will be caught and converted to service_call in the run method.

        This method should be implemented for a Stateful Check. It's called from run method.
        All Errors raised from stateful_check will be caught and converted to service_call in the run method.

        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @param state: StateType the current state for this check + persistence key.
        @return: tuple of state: StateType and an optional check error: Optional[CheckError] that is set as the new
        state.
        """
        raise NotImplementedError
