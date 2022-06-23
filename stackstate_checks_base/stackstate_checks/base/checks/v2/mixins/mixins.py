from abc import abstractmethod

from typing import Any


class CheckMixin(object):
    """
    CheckMixin is an interface that exposes additional functionality to the Agent Check base.
    """

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
        # Initialize AgentCheck's base class
        super(CheckMixin, self).__init__(*args, **kwargs)

    @abstractmethod
    def setup(self):  # type: () -> None
        """

        @return:None
        """
        raise NotImplementedError
