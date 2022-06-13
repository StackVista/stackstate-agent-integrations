import logging
import re

try:
    import state

    using_stub_state = False
except ImportError:
    from ..stubs import state

    using_stub_state = True


class StateApi(object):
    def __init__(self, check):
        self.check = check
        self.log = logging.getLogger('{}.{}'.format(__name__, self.check.name))
        if using_stub_state:
            self.log.warning("Using stub state api")

    def get_state(self, key):
        return state.get_state(self.check, self.check.check_id, self._state_id(key))

    def set_state(self, key, new_state):
        state.set_state(self.check, self.check.check_id, self._state_id(key), new_state)

    def _state_id(self, key):
        """
        State ID is used for filename where state is stored.
        It is constructed from sanitized `TopologyInstance.url` and provided key.
        """
        return '{}_{}'.format(self._instance_key_url_as_filename(), key)

    def _instance_key_url_as_filename(self):
        # type: () -> str
        """Returns url string sanitized from all characters that would prevent it to be used as a filename"""
        pattern = r"[^a-zA-Z0-9_-]"
        return re.sub(pattern, "", self.check.get_instance_key(self.check.instances[0]).url)
