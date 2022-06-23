from schematics import Model
from typing import Any, Dict, Optional, Union

from .stateful import StatefulMixin
from ....utils.transactional_api import TransactionApi


class TransactionalMixin(StatefulMixin):
    """
    Transactional registers the transactional hook to be used by the agent base and the check itself.
    """

    """
    TRANSACTIONAL_PERSISTENT_CACHE_KEY is the key that is used for the transactional persistent state
    """
    TRANSACTIONAL_PERSISTENT_CACHE_KEY = "transactional_check_state"  # type: str

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
        # Initialize AgentCheck's base class
        super(TransactionalMixin, self).__init__(*args, **kwargs)
        self.transaction = None  # type: Optional[TransactionApi]

    def set_state_transactional(self, new_state):  # type: (Union[Dict, Model]) -> None
        """

        @param new_state:
        @return:
        """
        self.transaction.set_state(self.TRANSACTIONAL_PERSISTENT_CACHE_KEY, new_state)

    def get_state_transactional(self):  # type: () -> Dict[str, Any]
        """

        @return:
        """
        return self.state.get(self.TRANSACTIONAL_PERSISTENT_CACHE_KEY, self.STATE_SCHEMA)

    def setup(self):  # type: () -> None
        """

        @return:
        """
        super(TransactionalMixin, self).setup()

        if self.transaction is not None:
            return None
        self.transaction = TransactionApi(self)
