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
        self.log.info("State API: Getting state for key: " + key)
        self.log.info("State API: Getting state for state key: " + self._get_state_key(key))
        self.log.info("State API: Getting state for check id: " + self.__check.check_id)

        current_state = state.get_state(self.__check, self.__check.check_id, self._get_state_key(key))

        self.log.info("State API: Retrieve state before unmarshalling the string: ")
        self.log.info(current_state)

        # If for any reason the retrieved state is None we can default to an unmarshal-able object
        if current_state is None:
            self.log.info("State API: Current State is None")
            return {}

        # If we did in fact receive a value back we can then attempt to unmarshal it
        try:
            if not schema:
                self.log.info("State API: Json Load State Value")
                return json.loads(current_state)

            if current_state and schema:
                self.log.info("State API: Schematic Json Load State Value")
                schema_state = schema(json.loads(current_state))
                schema_state.validate()
                return schema_state
        except TypeError as e:
            self.log.error("""Unable to unmarshal the latest persistent state,
                              Saved state may be in the incorrect format: {}""".format(current_state))
            raise Exception(e)

    def set(self, key, new_state):
        # type: (str, Union[Dict[str, Any], Model]) -> None
        """
        Dumps state to JSON string and sets it as a new state.
        """
        state.set_state(self.__check, self.__check.check_id, self._get_state_key(key), validate_state(new_state))

    def _get_state_key(self, key):
        # type: (str) -> str
        return generate_state_key(self.__check._get_instance_key().to_string(), key)
