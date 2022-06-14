import logging

from .state_api import generate_state_key

try:
    import transaction

    using_stub_transaction = False
except ImportError:
    from ..stubs import transaction

    using_stub_transaction = True


class TransactionApi(object):
    def __init__(self, check):
        self.check = check
        self.log = logging.getLogger('{}.{}'.format(__name__, self.check.name))
        if using_stub_transaction:
            self.log.warning("Using stub transactional api")

    def start(self):
        # type: () -> None
        """
        Start transaction.
        """
        transaction.start_transaction(self.check, self.check.check_id)

    def stop(self):
        # type: () -> None
        """
        Stop transaction.
        """
        transaction.stop_transaction(self.check, self.check.check_id)

    def set_state(self, key, state):
        # type: (str, str) -> None
        """
        Sets transactional state.
        """
        state_key = generate_state_key(self.check.instances[0].get("url", ""), key)
        transaction.set_transaction_state(self.check, self.check.check_id, state_key, state)
