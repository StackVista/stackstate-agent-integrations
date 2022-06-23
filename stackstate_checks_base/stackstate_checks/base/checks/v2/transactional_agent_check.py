from typing import Optional

from .base import AgentCheckV2
from .check_error import CheckError
from .mixins import TransactionalMixin
from .types import InstanceType, StateType


class TransactionalAgentCheck(TransactionalMixin, AgentCheckV2):
    """
    TransactionalAgentCheck is an alias for AgentCheckV2 with TransactionalMixin already mixed in. This is the preferred
    class to extend when writing a check that needs transactional state behaviour.
    """

    def check(self, instance):  # type: (InstanceType) -> Optional[CheckError]
        """
        Check implements the AgentCheckV2 check function and automagically handles the transaction for this check run.
        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @return: Optional[CheckError] if an error occurs during the check the exception / error is returned.
        """

        # get current state > call the check > set the transaction state
        self.transaction.start()
        current_state = self.get_transaction_state()
        new_state, check_error = self.transactional_check(instance, current_state)

        if check_error:
            self.transaction.discard(check_error.to_string())
            return check_error

        self.set_transaction_state(new_state)
        self.transaction.stop()

        return

    def transactional_check(self, instance, state):
        # type: (InstanceType, StateType) -> (StateType, Optional[CheckError])
        """
        This method should be implemented for a Transactional Check. It's called from run method.
        All Errors raised from transactional_check will be caught and converted to service_call in the run method.

        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @param state: StateType the current state for this check + persistence key.
        @return: tuple of state: StateType and an optional check error: Optional[CheckError] that is set as the
        transaction state.
        """
        raise NotImplementedError
