import json
import logging
from typing import Union, Dict, Any, Optional, Type

from schematics import Model

from .state_common import generate_state_key, validate_state

try:
    import state

    using_stub_state = False
except ImportError:
    from ..stubs import state

    using_stub_state = True


class StateApi(object):
    ZERO_VALUE = "{}"

    def __init__(self, check):
        self.__check = check
        self.log = logging.getLogger("{}.{}".format(__name__, self.__check.name))
        if using_stub_state:
            self.log.warning("Using stub state api")

    def get(self, key, schema=None):
        # type: (str, Optional[Type[Model]]) -> Union[Dict[str, Any], Model]
        """
        Reads state stored as JSON string and returns it as dictionary.
        """
        current_state = state.get_state(self.__check, self.__check.check_id, self._get_state_key(key))

        if not schema:
            return json.loads(current_state)

        if current_state and schema:
            schema_state = schema(json.loads(current_state))
            schema_state.validate()
            return schema_state

    def set(self, key, new_state):
        # type: (str, Union[Dict[str, Any], Model]) -> None
        """
        Dumps state to JSON string and sets it as a new state.
        """
        state.set_state(self.__check, self.__check.check_id, self._get_state_key(key), validate_state(new_state))

    def _get_state_key(self, key):
        # type: (str) -> str
        return generate_state_key(self.__check._get_instance_key().to_string(), key)
