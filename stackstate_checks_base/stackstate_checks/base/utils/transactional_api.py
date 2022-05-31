try:
    import transaction

    using_stub_transaction = False
except ImportError:
    from ..stubs import transaction

    using_stub_transaction = True


class TransactionApi(object):
    def __init__(self, check):
        self.check = check

    def start_transaction(self):
        transaction.start_transaction(self.check,
                                      self.check.check_id)

    def stop_transaction(self):
        transaction.stop_transaction(self.check,
                                     self.check.check_id)
