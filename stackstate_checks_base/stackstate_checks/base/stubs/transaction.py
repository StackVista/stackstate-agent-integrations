# (C) StackState, Inc. 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.base.stubs import state


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
        self._state = state

    def _ensure_transaction(self, check_id):
        # TODO: does transaction needs unique ID?
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
        return self._ensure_transaction(check_id)

    def set_transaction_state(self, check, check_id, key, new_state):
        if self._is_transaction_completed(check_id):
            self._state.set(check, check_id, key, new_state)

    def assert_transaction(self, check_id):
        assert self._is_transaction_completed(check_id) is True

    def reset(self):
        self._transactions = {}

    def _is_transaction_completed(self, check_id):
        if self.get_transaction(check_id)["started"] and self.get_transaction(check_id)["stopped"]:
            return True
        return False


# Use the stub as a singleton
transaction = TransactionStub()
