from typing import Optional

from .base import AgentCheckV2
from .mixins import TransactionalMixin
from .types import InstanceType, StateType, CheckResponse


class TransactionalAgentCheck(TransactionalMixin, AgentCheckV2):
    """
    TransactionalAgentCheck is an alias for AgentCheckV2 with TransactionalMixin already mixed in. This is the preferred
    class to extend when writing a check that needs transactional state behaviour.
    """

    def check(self, instance):  # type: (InstanceType) -> CheckResponse
        """
        Check implements the AgentCheckV2 check function and automagically handles the transaction for this check run.
        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @return: Optional[CheckError] if an error occurs during the check the exception / error is returned.
        """

        # get current state > call the check > set the transaction state
        self.transaction.start()
        current_persistent_state = self.get_state()
        current_transactional_state = self.get_transaction_state()

        check_response = self.transactional_check(instance, current_transactional_state, current_persistent_state)

        self.set_state(check_response.persistent_state)

        if check_response and check_response.check_error:
            self.transaction.discard(check_response.check_error.message)
            return check_response

        self.set_transaction_state(check_response.transactional_state)

        self.transaction.stop()

        return check_response

    def transactional_check(self, instance, transactional_state, persistent_state):
        # type: (InstanceType, StateType, StateType) -> CheckResponse
        """
        This method should be implemented for a Transactional Check. It's called from run method.
        All Errors raised from transactional_check will be caught and converted to service_call in the run method.

        @param instance: InstanceType instance of the check implemented by get_instance_key().
        @param transactional_state: StateType the current transactional state for this check + persistence key.
        @param persistent_state: StateType the current persistent state for this check + persistence key.
        @return: tuple of state: StateType and an optional check error: Optional[CheckError] that is set as the
        transaction state.
        """
        raise NotImplementedError
