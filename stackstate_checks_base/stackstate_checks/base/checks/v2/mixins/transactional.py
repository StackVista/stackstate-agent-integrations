from typing import Any, Optional

from .stateful import StatefulMixin
from ..types import StateType
from ....utils.transactional_api import TransactionApi
from ....utils.validations_utils import CheckBaseModel


class TransactionalMixin(StatefulMixin):
    """
    TransactionalMixin extends the Agent Check base with the Transaction API allowing Agent Checks to start making
    stateful transactions that are persisted when a transaction is successful.
    """

    """
    TRANSACTIONAL_PERSISTENT_CACHE_KEY is the key that is used for the transactional persistent state
    """
    TRANSACTIONAL_PERSISTENT_CACHE_KEY = "transactional_check_state"  # type: str

    """
    TRANSACTIONAL_STATE_SCHEMA allows checks to specify a schematics Schema that is used for the transactional state in
    self.check.
    """
    TRANSACTIONAL_STATE_SCHEMA = None  # type: Optional[CheckBaseModel]

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        """

        """
        # Initialize AgentCheck's base class
        super(TransactionalMixin, self).__init__(*args, **kwargs)
        self.transaction = None  # type: Optional[TransactionApi]

    def set_transaction_state(self, new_state):  # type: (StateType) -> None
        """
        set_transaction_state uses the TransactionApi to set the transaction state for the
        TRANSACTIONAL_PERSISTENT_CACHE_KEY with the value of new_state.
        @param new_state: StateType is the new transaction state to be set
        @return:
        """
        self.transaction.set_state(self.TRANSACTIONAL_PERSISTENT_CACHE_KEY, new_state)

    def get_transaction_state(self):  # type: () -> StateType
        """
        get_state uses the StateApi to retrieve the state for the TRANSACTIONAL_PERSISTENT_CACHE_KEY.

        If a TRANSACTIONAL_STATE_SCHEMA is defined the state is cast to the TRANSACTIONAL_STATE_SCHEMA.

        @return: StateType the state for the TRANSACTIONAL_PERSISTENT_CACHE_KEY. Defaults to empty dictionary or an
        "empty" TRANSACTIONAL_STATE_SCHEMA.
        """
        return self.state.get(self.TRANSACTIONAL_PERSISTENT_CACHE_KEY, self.TRANSACTIONAL_STATE_SCHEMA)

    def setup(self):  # type: () -> None
        """
        setup is used to initialize the TransactionApi and set the transaction variable to be used in checks.

        @return: None
        """
        super(TransactionalMixin, self).setup()

        if self.transaction is not None:
            return None
        self.transaction = TransactionApi(self)
