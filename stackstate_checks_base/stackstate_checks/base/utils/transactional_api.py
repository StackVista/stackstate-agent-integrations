import logging

import json
from typing import Union, Dict, Any

from .state_api import generate_state_key
from .state_common import validate_state
from .validations_utils import CheckBaseModel

try:
    import transaction
    import state

    using_stub_transaction = False
except ImportError:
    from ..stubs import transaction
    from ..stubs import state

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
        # type: (str, Union[Dict[str, Any], CheckBaseModel]) -> None
        """
        Dumps transactional state to JSON string and sets it as a new state.
        """
        state_key = generate_state_key(self.__check._get_instance_key().to_string(), key)
        transaction.set_transaction_state(self.__check, self.__check.check_id, state_key, validate_state(new_state))

        # Stub only functionality
        # Because transactional state does not have a get and uses the StateApi to get its state in the next run
        # we need to set this same behaviour over here for testing
        # To do this we will set State from this transaction
        if using_stub_transaction:
            state.set_state(self.__check, self.__check.check_id, state_key, json.dumps(new_state))
