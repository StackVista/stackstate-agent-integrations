import logging

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
        transaction.start_transaction(self.check, self.check.check_id)

    def stop(self):
        transaction.stop_transaction(self.check, self.check.check_id)

    def set_state(self, key, state):
        # TODO: construct state key
        transaction.set_transaction_state(self.check, self.check.check_id, key, state)
