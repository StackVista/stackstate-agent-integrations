import json
import logging
from typing import Union, Dict, Any

from schematics import Model

from .common import sanitize_url_as_valid_filename

try:
    import state

    using_stub_state = False
except ImportError:
    from ..stubs import state

    using_stub_state = True


class StateApi(object):
    def __init__(self, check):
        self.check = check
        self.log = logging.getLogger("{}.{}".format(__name__, self.check.name))
        if using_stub_state:
            self.log.warning("Using stub state api")

    def get(self, key):
        # type: (str) -> Dict[str, Any]
        """
        Reads state stored as JSON string and returns it as dictionary.
        """
        current_state = state.get_state(self.check, self.check.check_id, self._state_id(key))
        if not current_state:
            current_state = "{}"
        return json.loads(current_state)

    def set(self, key, new_state):
        # type: (str, Union[Dict[str, Any], Model]) -> None
        """
        Dumps state to JSON string and sets it as a new state.
        """
        if isinstance(new_state, dict):
            pass
        elif isinstance(new_state, Model):
            new_state = new_state.to_primitive()
        else:
            raise ValueError(
                "Got unexpected {} for new state, expected dictionary or schematics.Model".format(type(state))
            )
        new_state = json.dumps(new_state)
        state.set_state(self.check, self.check.check_id, self._state_id(key), new_state)

    def _state_id(self, key):
        # type: (str) -> str
        """
        State ID is used for filename where state is stored.
        It is constructed from sanitized `TopologyInstance.url` and provided key.
        """
        return "{}_{}".format(sanitize_url_as_valid_filename(self.check.instances[0].get("url", "")), key)
