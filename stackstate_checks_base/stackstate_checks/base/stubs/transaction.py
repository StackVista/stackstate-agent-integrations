# (C) StackState, Inc. 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from .state import state


class TransactionStubAsserts(object):
    def assert_completed_transaction(self, check_id, assert_bool):
        assert self._is_transaction_completed(check_id) is assert_bool

    def assert_discarded_transaction(self, check_id, assert_bool):
        assert self._transactions[check_id].discarded is assert_bool

    def assert_started_transaction(self, check_id, assert_bool):
        assert self._transactions[check_id].started is assert_bool

    def assert_stopped_transaction(self, check_id, assert_bool):
        assert self._transactions[check_id].stopped is assert_bool


class TransactionStub(TransactionStubAsserts):
    """
    This implements the methods defined by the Agent's [C bindings]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/rtloader/common/builtins/transaction.c)
    which in turn call the [Go backend]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/pkg/collector/python/transactional_api.go).
    It also provides utility methods for test assertions.
    """

    def __init__(self):
        self._transactions = {}
        self._state = state

    def _ensure_transaction(self, check_id):
        if check_id not in self._transactions:
            self._transactions[check_id] = {
                "started": False,
                "discarded": False,
                "stopped": False
            }
        return self._transactions[check_id]

    def start_transaction(self, check, check_id):
        self._ensure_transaction(check_id)["started"] = True

    def stop_transaction(self, check, check_id):
        self._ensure_transaction(check_id)["stopped"] = True

    def discard_transaction(self, check, check_id, discard_reason):
        self._ensure_transaction(check_id)["discarded"] = True
        self._ensure_transaction(check_id)["discard_reason"] = discard_reason

    def get_transaction(self, check_id):
        return self._ensure_transaction(check_id)

    def set_transaction_state(self, check, check_id, key, new_state):
        if not self._is_transaction_completed(check_id):
            self._state.set_state(check, check_id, key, new_state)

    def reset(self):
        self._transactions = {}

    def _is_transaction_completed(self, check_id):
        if self.get_transaction(check_id)["started"] and self.get_transaction(check_id)["stopped"]:
            return True
        return False


# Use the stub as a singleton
transaction = TransactionStub()
