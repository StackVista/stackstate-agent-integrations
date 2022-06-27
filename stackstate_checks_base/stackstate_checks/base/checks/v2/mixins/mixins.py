from abc import abstractmethod

from typing import Any


class CheckMixin(object):
    """
    CheckMixin is an interface that exposes additional functionality to an Agent Check.
    """

    def __init__(self, *args, **kwargs):  # type: (*Any, **Any) -> None
        """
        CheckMixin initializes the Agent Check V2 base class and passes the args and kwargs to the super init.

        @param args: *Any
        @param kwargs: **Any
        """
        # Initialize AgentCheck's base class
        super(CheckMixin, self).__init__(*args, **kwargs)

    @abstractmethod
    def setup(self):  # type: () -> None
        """
        setup must be overridden by the CheckMixin's to initialize their functionality for the check runs.
        @return:None
        """
        raise NotImplementedError
