from schematics import Model
from typing import Any, Optional, Type, Union, Dict

from .mixins import CheckMixin
from ....utils.state_api import StateApi


class StatefulMixin(CheckMixin):
    """

    """

    """
    STATE_SCHEMA allows checks to specify a schematics Schema that is used for the state in self.check
    """
    STATE_SCHEMA = None  # type: Type[Model]

    """
    PERSISTENT_CACHE_KEY is the key that is used for the persistent state
    """
    PERSISTENT_CACHE_KEY = "check_state"  # type: str

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        """
        - **name** (_str_) - the name of the check
        - **init_config** (_dict_) - the `init_config` section of the configuration.
        - **agentConfig** (_dict_) - deprecated
        - **instance** (_List[dict]_) - a one-element list containing the instance options from the
                configuration file (a list is used to keep backward compatibility with
                older versions of the Agent).
        """
        super(StatefulMixin, self).__init__(*args, **kwargs)
        self.state = None  # type: Optional[StateApi]

    def set_state(self, new_state):  # type: (Union[Dict, Model]) -> None
        """

        @param new_state:
        @return:
        """
        self.state.set(self.PERSISTENT_CACHE_KEY, new_state)

    def get_state(self):  # type: () -> Dict[str, Any]
        """

        @return:
        """
        return self.state.get(self.PERSISTENT_CACHE_KEY, self.STATE_SCHEMA)

    def setup(self):  # type: () -> None
        """

        @return:
        """
        if self.state is not None:
            return None
        self.state = StateApi(self)
