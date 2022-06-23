from schematics import Model
from typing import Any, Dict, Optional, Union

from .base import AgentCheckV2
from .check_error import CheckError
from .instance_type import InstanceType
from .mixins import StatefulMixin


class StatefulAgentCheck(StatefulMixin, AgentCheckV2):
    def check(self, instance):
        # type: (InstanceType) -> Optional[CheckError]

        self.setup()
        # get current state > call the check > set the state
        current_state = self.get_state()
        new_state, check_error = self.stateful_check(instance, current_state)

        if check_error:
            return check_error

        self.set_state(new_state)

        return

    def stateful_check(self, instance, state):
        # type: (InstanceType, Union[Dict[str, Any], Model]) -> (Dict[str, Any], Optional[CheckError])
        """
        This method should be implemented for a Stateful Check. It's called from run method.
        All Errors raised from stateful_check will be caught and converted to service_call in the run method.

        - **instance** instance (schema type)
        - **state** existing state in Json TODO: maybe also schema type for state
        returns new state
        """
        raise NotImplementedError
