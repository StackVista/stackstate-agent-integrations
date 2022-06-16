import logging

import json
from typing import Union, Dict, Any
from schematics import Model

from .state_api import generate_state_key

try:
    import transaction

    using_stub_transaction = False
except ImportError:
    from ..stubs import transaction

    using_stub_transaction = True


class TransactionApi(object):
    def __init__(self, check):
        self.__check = check
        self.log = logging.getLogger('{}.{}'.format(__name__, self.__check.name))
        if using_stub_transaction:
            self.log.warning("Using stub transactional api")

    def start(self):
        # type: () -> None
        """
        Start transaction.
        """
        transaction.start_transaction(self.__check, self.__check.check_id)

    def stop(self):
        # type: () -> None
        """
        Stop transaction.
        """
        transaction.stop_transaction(self.__check, self.__check.check_id)

    def discard(self, discard_reason):
        # type (str) -> None
        """
        Discard the current transaction.
        """
        transaction.discard_transaction(self.__check, self.__check.check_id, discard_reason)

    def set_state(self, key, new_state):
        # type: (str, Union[Dict[str, Any], Model]) -> None
        """
        Dumps transactional state to JSON string and sets it as a new state.
        """
        if isinstance(new_state, dict):
            pass
        elif isinstance(new_state, Model):
            new_state = new_state.to_primitive()
        else:
            raise ValueError(
                "Got unexpected {} for new state, expected dictionary or schematics.Model".format(type(new_state))
            )
        state = json.dumps(new_state)

        state_key = generate_state_key(self.__check._get_instance_key().to_string(), key)
        transaction.set_transaction_state(self.__check, self.__check.check_id, state_key, state)
