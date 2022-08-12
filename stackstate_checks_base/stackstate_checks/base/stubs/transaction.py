# (C) StackState, Inc. 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import json

from stackstate_checks.base.utils.state_common import generate_state_key


class TransactionStub(object):
    """
    This implements the methods defined by the Agent's [C bindings]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/rtloader/common/builtins/transaction.c)
    which in turn call the [Go backend]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/pkg/collector/python/transactional_api.go).
    It also provides utility methods for test assertions.
    """

    def __init__(self):
        # The values captured in the transactional state
        self._transactions = {}
        # Steps that the transactional state followed for example start, stopped etc
        self._transaction_steps = {}

    def reset(self):
        self._transactions = {}
        self._transaction_steps = {}

    # Make sure that the transaction steps exists for the check_id if not set the _init_transaction_steps default
    def _ensure_transaction_steps(self, check_id):
        if check_id not in self._transaction_steps:
            self._transaction_steps[check_id] = {
                "started": False,
                "discarded": False,
                "stopped": False,
                "discard_reason": None
            }
        return self._transaction_steps[check_id]

    # Make sure that the transaction state exists for the check_id if not create an empty {} state
    def _ensure_transaction_state(self, check_id):
        if check_id not in self._transactions:
            self._transactions[check_id] = {}
        return self._transactions[check_id]

    # Monitor when a transaction started
    def start_transaction(self, check, check_id):
        self._ensure_transaction_steps(check_id)["started"] = True
        self._ensure_transaction_steps(check_id)["stopped"] = False

    # Monitor when a transaction stopped
    def stop_transaction(self, check, check_id):
        self._ensure_transaction_steps(check_id)["started"] = False
        self._ensure_transaction_steps(check_id)["stopped"] = True

    # Monitor when if a transaction was discarded
    def discard_transaction(self, check, check_id, discard_reason):
        self._ensure_transaction_steps(check_id)["discarded"] = True
        self._ensure_transaction_steps(check_id)["discard_reason"] = str(discard_reason)

    # Set a new value for the transactional state
    def set_transaction_state(self, check, check_id, key, new_state):
        if not self._transaction_completed_successfully(check_id):
            self._ensure_transaction_state(check_id)[key] = new_state

    def _transaction_completed_successfully(self, check_id):
        transactions_steps_state = self._ensure_transaction_steps(check_id)

        return transactions_steps_state["started"] is False and \
            transactions_steps_state["stopped"] is True and \
            transactions_steps_state["discarded"] is False

    def assert_transaction_success(self, check_id):
        assert self._transaction_completed_successfully(check_id) is True

    def assert_started_transaction(self, check_id, expected):
        assert self._ensure_transaction_steps(check_id)["started"] is expected

    def assert_stopped_transaction(self, check_id, expected):
        assert self._ensure_transaction_steps(check_id)["stopped"] is expected

    def assert_discarded_transaction(self, check_id, expected):
        assert self._ensure_transaction_steps(check_id)["discarded"] is expected

    def assert_discarded_transaction_reason(self, check_id, expected):
        assert self._ensure_transaction_steps(check_id)["discard_reason"] is expected

    def assert_completed_transaction(self, check_id):
        assert self._ensure_transaction_steps(check_id)["started"] is False and \
               self._ensure_transaction_steps(check_id)["stopped"] is True

    def assert_transaction_state(self, check, check_id, expected_key, expected_value):
        transaction_state_key = generate_state_key(check._get_instance_key().to_string(),
                                                   check.TRANSACTIONAL_PERSISTENT_CACHE_KEY)
        transaction_state_dict = json.loads(self._ensure_transaction_state(check_id)[transaction_state_key])

        assert transaction_state_dict.get(expected_key) is expected_value


# Use the stub as a singleton
transaction = TransactionStub()
