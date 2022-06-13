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
        self._state[key] = new_state

    def get_state(self, check, check_id, key):
        return self._state.get(key, {})


state = StateStub()
