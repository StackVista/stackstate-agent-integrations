# (C) StackState, Inc. 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

class TransactionStub(object):
    """
    This implements the methods defined by the Agent's [C bindings]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/rtloader/common/builtins/transaction.c)
    which in turn call the [Go backend]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/pkg/collector/python/transactional_api.go).
    It also provides utility methods for test assertions.
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

    def get_transaction(self, check_id):
        return self._transactions[check_id]

    def set_transaction_state(self, check, check_id, key, state):
        pass
        # TODO: call state_set state if transaction stopped

    def assert_transaction(self, check_id):
        assert self.get_transaction(check_id) == {
            "started": True,
            "stopped": True
        }

    def reset(self):
        self._transactions = {}


# Use the stub as a singleton
transaction = TransactionStub()
