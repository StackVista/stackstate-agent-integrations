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
        self.__check = check
        self.log = logging.getLogger("{}.{}".format(__name__, self.__check.name))
        if using_stub_state:
            self.log.warning("Using stub state api")

    def get(self, key):
        # type: (str) -> Dict[str, Any]
        """
        Reads state stored as JSON string and returns it as dictionary.
        """
        current_state = state.get_state(self.__check, self.__check.check_id, self._get_state_key(key))
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
        state.set_state(self.__check, self.__check.check_id, self._get_state_key(key), new_state)

    def _get_state_key(self, key):
        # type: (str) -> str
        return generate_state_key(self.__check._get_instance_key().to_string(), key)


def generate_state_key(instance_url, key):
    # type: (str, str) -> str
    """
    State key is used for a filename of the file where state is stored.
    It is constructed from sanitized `TopologyInstance.url` and provided key.
    """
    return "{}_{}".format(sanitize_url_as_valid_filename(instance_url), key)
