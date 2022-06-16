from abc import ABCMeta

from base import AgentCheck
import copy
import json
import traceback
from typing import Any, Set, Dict, Sequence, List, Optional, Union, AnyStr, TypeVar
from six import PY3
from schematics import Model
from ..utils.common import to_string
from ..utils.transactional_api import TransactionApi
from ..utils.state_api import StateApi

_InstanceType = TypeVar('_InstanceType', Model, Dict[str, Any])

DEFAULT_RESULT = to_string(b'')


class CheckError(Exception):
    """
    Agent error that needs to be converted to Critical Service Check
    """

    def to_string(self):
        # type: () -> str
        return "check error: {}".format(self.message)


class AgentCheckV2(AgentCheck):

    def check(self, instance):
        raise NotImplementedError

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
        super(AgentCheckV2, self).__init__(*args, **kwargs)

    def run(self):
        # type: () -> str
        """
        Runs stateful check.
        """
        instance_tags = None
        try:
            # create integration instance components for monitoring purposes
            self.create_integration_instance()

            # Initialize APIs
            self._init_health_api()

            # create a copy of the check instance, get state if any and add it to the instance object for the check
            instance = self.instances[0]
            check_instance = copy.deepcopy(instance)
            check_instance = self._get_instance_schema(check_instance)
            instance_tags = check_instance.get("instance_tags", [])

            check_result = self.check(check_instance)

            if check_result:
                raise check_result

            result = DEFAULT_RESULT
            msg = "{} check was processed successfully".format(self.name)
            self.service_check(self.name, AgentCheck.OK, tags=instance_tags, message=msg)
        except Exception as e:
            result = json.dumps([
                {
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                }
            ])
            self.log.exception(str(e))
            self.service_check(self.name, AgentCheck.CRITICAL, tags=instance_tags, message=str(e))
        finally:
            if self.metric_limiter:
                self.metric_limiter.reset()

        return result


class CheckMixin(object):
    """
    CheckMixin is used to register a agent hook to be used by the agent base and the check itself.
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

    def check(self, instance):
        # type: (_InstanceType) -> Optional[CheckError]
        return CheckError(NotImplementedError)


class State(CheckMixin):
    PERSISTENT_CACHE_KEY = "check_state"

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
        super(State, self).__init__(*args, **kwargs)
        self._state = None  # type: Optional[StateApi]

    def set_state(self, new_state):
        # type: (Union[Dict, Model]) -> None
        """
        Set new checks state.
        """
        self._state.set(self.PERSISTENT_CACHE_KEY, new_state)

    def get_state(self):
        # type: () -> Dict[str, Any]
        """
        Gets existing checks state.
        """
        return self._state.get(self.PERSISTENT_CACHE_KEY)

    def _init_state_api(self):
        # type: () -> None
        if self._state is not None:
            return None
        self._state = StateApi(self)

    def check(self, instance):
        raise NotImplementedError


class Stateful(State):
    """
    StateFulMixin registers the Stateful hook to be used by the agent base and the check itself.
    """

    def check(self, instance):
        # type: (_InstanceType) -> Optional[CheckError]

        self._init_state_api()
        # get current state > call the check > set the state
        current_state = self.get_state()
        new_state, check_error = self.stateful_check(instance, current_state)

        if check_error:
            return check_error

        self.set_state(new_state)

        return

    def stateful_check(self, instance, state):
        # type: (_InstanceType, Union[Dict[str, Any], Model]) -> (Dict[str, Any], Optional[CheckError])
        """
        This method should be implemented for a Stateful Check. It's called from run method.
        All Errors raised from stateful_check will be caught and converted to service_call in the run method.

        - **instance** instance (schema type)
        - **state** existing state in Json TODO: maybe also schema type for state
        returns new state
        """
        raise NotImplementedError


class Transactional(State):
    """
    Transactional registers the transactional hook to be used by the agent base and the check itself.
    """
    TRANSACTIONAL_PERSISTENT_CACHE_KEY = "transactional_check_state"

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
        super(Transactional, self).__init__(*args, **kwargs)
        self.transaction = None  # type: Optional[TransactionApi]

    def check(self, instance):
        # type: (_InstanceType) -> Optional[CheckError]

        self._init_state_api()
        self._init_transactional_api()

        # get current state > call the check > set the transaction state
        self.transaction.start()
        current_state = self.get_state_transactional()
        new_state, check_error = self.transactional_check(instance, current_state)

        if check_error:
            self.transaction.discard(check_error.to_string())
            return check_error

        self.set_state_transactional(new_state)
        self.transaction.stop()

        return

    def set_state_transactional(self, new_state):
        # type: (Union[Dict, Model]) -> None
        """
        Set new checks state.
        """
        self.transaction.set_state(self.TRANSACTIONAL_PERSISTENT_CACHE_KEY, new_state)

    def get_state_transactional(self):
        # type: () -> Dict[str, Any]
        """
        Gets existing checks state.
        """
        return self._state.get(self.TRANSACTIONAL_PERSISTENT_CACHE_KEY)

    def transactional_check(self, instance, state):
        # type: (_InstanceType, Union[Dict[str, Any], Model]) -> (Dict[str, Any], Optional[CheckError])
        """
        This method should be implemented for a Stateful Check. It's called from run method.
        All Errors raised from stateful_check will be caught and converted to service_call in the run method.

        - **instance** instance (schema type)
        - **state** existing state in Json TODO: maybe also schema type for state
        returns new state
        """
        raise NotImplementedError

    def _init_transactional_api(self):
        # type: () -> None
        if self.transaction is not None:
            return None
        self.transaction = TransactionApi(self)
