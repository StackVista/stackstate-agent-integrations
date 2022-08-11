import json

from stackstate_checks.base.utils.state_common import generate_state_key


class StateStub(object):
    """
    This implements the methods defined by the Agent's [C bindings]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/rtloader/common/builtins/state.c)
    which in turn call the [Go backend]
    (https://gitlab.com/stackvista/agent/stackstate-agent/-/blob/master/pkg/collector/python/state_api.go).
    """

    def __init__(self):
        self._state = {}

    def set_state(self, check, check_id, key, new_state):
        print("Using stub state for setting state")
        self._state[key] = new_state

    def get_state(self, check, check_id, key):
        print("Using stub state for getting state")
        return self._state.get(key, "{}")

    def reset(self):
        print("Resetting stub state")
        self._state = {}

    def assert_state(self, check, expected_key, expected_value):
        # Generate the persistent key to be used in retrieving the saved persistent state
        persistent_state_key = generate_state_key(check._get_instance_key().to_string(), check.PERSISTENT_CACHE_KEY)
        # Use the key to retrieve the persistent state and parse the dict to be tested
        persistent_state_dict = json.loads(self.get_state(check, check.check_id, persistent_state_key))

        assert persistent_state_dict.get(expected_key) == expected_value

    def assert_state_is_empty(self, check):
        # Generate the persistent key to be used in retrieving the saved persistent state
        persistent_state_key = generate_state_key(check._get_instance_key().to_string(), check.PERSISTENT_CACHE_KEY)
        # Use the key to retrieve the persistent state and parse the dict to be tested
        persistent_state = self.get_state(check, check.check_id, persistent_state_key)

        assert persistent_state == "{}"


# Use the stub as a singleton
state = StateStub()
