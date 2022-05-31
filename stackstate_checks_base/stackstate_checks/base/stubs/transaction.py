from __future__ import division


class TransactionStub(object):
    """
    Mainly used for unit testing checks, this stub makes possible to execute
    a check without a running Agent.
    """

    def __init__(self):
        self._transactions = {}

    def _ensure_transaction(self, check_id):
        if check_id not in self._transactions:
            self._transactions[check_id] = {
                "started": False,
                "stopped": False
            }
        return self._transactions[check_id]

    def start_transaction(self, check, check_id):
        self._ensure_transaction(check_id)["started"] = True

    def stop_transaction(self, check, check_id):
        self._ensure_transaction(check_id)["stopped"] = True


# Use the stub as a singleton
transaction = TransactionStub()
