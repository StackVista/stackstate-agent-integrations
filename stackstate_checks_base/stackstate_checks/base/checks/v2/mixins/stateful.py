from typing import Any, Optional

from .mixins import CheckMixin
from ..types import StateType
from ....utils.state_api import StateApi
from ....utils.validations_utils import CheckBaseModel


class StatefulMixin(CheckMixin):
    """
    StatefulMixin extends the Agent Check base with the State API allowing Agent Checks to start persisting data.
    """

    """
    STATE_SCHEMA allows checks to specify a schematics Schema that is used for the state in self.check.
    """
    STATE_SCHEMA = None  # type: Optional[CheckBaseModel]

    """
    PERSISTENT_CACHE_KEY is the key that is used for the state of the agent check.
    """
    PERSISTENT_CACHE_KEY = "check_state"  # type: str

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        """
        StatefulMixin initializes the Agent Check V2 base class and passes the args and kwargs to the super init, and
        declares the state variable which is an Optional[StateApi] defaulted to None. It is initialized in setup.

        @param args: *Any
        @param kwargs: **Any
        """
        super(StatefulMixin, self).__init__(*args, **kwargs)
        self.state = None  # type: Optional[StateApi]

    def set_state(self, new_state):  # type: (StateType) -> None
        """
        set_state uses the StateApi to persist state for the PERSISTENT_CACHE_KEY.
        @param new_state: StateType is the new state that should be persisted.
        @return: None
        """
        self.state.set(self.PERSISTENT_CACHE_KEY, new_state)

    def get_state(self):  # type: () -> StateType
        """
        get_state uses the StateApi to retrieve the state for the PERSISTENT_CACHE_KEY.

        If a STATE_SCHEMA is defined the state is cast to the STATE_SCHEMA.

        @return: StateType the state for the PERSISTENT_CACHE_KEY. Defaults to empty dictionary or an empty
        STATE_SCHEMA.
        """
        return self.state.get(self.PERSISTENT_CACHE_KEY, self.STATE_SCHEMA)

    def setup(self):  # type: () -> None
        """
        setup is used to initialize the StateApi and set the state variable to be used in checks.

        @return: None
        """
        super(StatefulMixin, self).setup()

        if self.state is not None:
            return None
        self.state = StateApi(self)
