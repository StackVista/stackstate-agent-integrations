import copy
import json
import traceback

from schematics import Model
from typing import Any, Dict, Optional, Union, TypeVar, Type

from .base import AgentCheck
from ..utils.common import to_string
from ..utils.health_api import HealthApi, HealthStream
from ..utils.state_api import StateApi
from ..utils.transactional_api import TransactionApi

try:
    import topology

    using_stub_topology = False
except ImportError:
    from ..stubs import topology

    using_stub_topology = True

_InstanceType = TypeVar('_InstanceType', Model, Dict[str, Any])

DEFAULT_RESULT = to_string(b'')


class CheckError(Exception):
    """
    Agent error that needs to be converted to Critical Service Check
    """

    def to_string(self):
        # type: () -> str
        return "check error: {}".format(self.message)


class CheckMixin(object):
    """
    CheckMixin is used to register an agent hook to be used by the agent base and the check itself.
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

    def setup(self):  # type: () -> None
        raise NotImplementedError


class Health(CheckMixin):

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
        super(Health, self).__init__(*args, **kwargs)
        # self._get_instance_schema =
        # self.instance =
        self.health = None  # type: Optional[HealthApi]

    def get_health_stream(self, instance):
        # type: (_InstanceType) -> Optional[HealthStream]
        """
        Integration checks can override this if they want to be producing a health stream. Defining this will
        enable self.health() calls

        :return: a class extending HealthStream
        """
        return None

    def setup(self):  # type: () -> None
        if self.health is not None:
            return None

        stream_spec = self.get_health_stream(self._get_instance_schema(self.instance))
        if stream_spec:
            # collection_interval should always be set by the agent
            collection_interval = self.instance['collection_interval']
            repeat_interval_seconds = stream_spec.repeat_interval_seconds or collection_interval
            expiry_seconds = stream_spec.expiry_seconds
            # Only apply a default expiration when we are using sub_streams
            if expiry_seconds is None:
                if stream_spec.sub_stream != "":
                    expiry_seconds = repeat_interval_seconds * 4
                else:
                    # Explicitly disable expiry setting it to 0
                    expiry_seconds = 0
            self.health = HealthApi(self, stream_spec, expiry_seconds, repeat_interval_seconds)


class Stateful(CheckMixin):
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
        super(Stateful, self).__init__(*args, **kwargs)
        self.state = None  # type: Optional[StateApi]

    def set_state(self, new_state):
        # type: (Union[Dict, Model]) -> None
        """
        Set new checks state.
        """
        self.state.set(self.PERSISTENT_CACHE_KEY, new_state)

    def get_state(self):
        # type: () -> Dict[str, Any]
        """
        Gets existing checks state.
        """
        return self.state.get(self.PERSISTENT_CACHE_KEY, self.STATE_SCHEMA)

    def setup(self):
        # type: () -> None
        if self.state is not None:
            return None
        self.state = StateApi(self)


class Transactional(Stateful):
    """
    Transactional registers the transactional hook to be used by the agent base and the check itself.
    """

    """
    TRANSACTIONAL_PERSISTENT_CACHE_KEY is the key that is used for the transactional persistent state
    """
    TRANSACTIONAL_PERSISTENT_CACHE_KEY = "transactional_check_state"  # type: str

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
        return self.state.get(self.TRANSACTIONAL_PERSISTENT_CACHE_KEY, self.STATE_SCHEMA)

    def setup(self):
        # type: () -> None
        super(Transactional, self).setup()

        if self.transaction is not None:
            return None
        self.transaction = TransactionApi(self)


class AgentCheckV2Base(AgentCheck):

    def check(self, instance):
        # type: (_InstanceType) -> Optional[CheckError]
        raise NotImplementedError

    def setup(self):
        # type: () -> None
        pass

    def on_success(self):
        # type: () -> None
        pass

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
        super(AgentCheckV2Base, self).__init__(*args, **kwargs)

    def run(self):
        # type: () -> str
        """
        Runs stateful check.
        """
        instance_tags = None
        try:
            # start auto snapshot if with_snapshots is set to True
            if self._get_instance_key().with_snapshots:
                topology.submit_start_snapshot(self, self.check_id, self._get_instance_key_dict())

            # create integration instance components for monitoring purposes
            self.create_integration_instance()

            # Call setup on the mixins
            self.setup()

            # create a copy of the check instance, get state if any and add it to the instance object for the check
            instance = self.instances[0]
            check_instance = copy.deepcopy(instance)
            check_instance = self._get_instance_schema(check_instance)
            instance_tags = check_instance.get("instance_tags", [])

            check_result = self.check(check_instance)

            if check_result:
                raise check_result

            # stop auto snapshot if with_snapshots is set to True
            if self._get_instance_key().with_snapshots:
                topology.submit_stop_snapshot(self, self.check_id, self._get_instance_key_dict())

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


class AgentCheckV2(Health, AgentCheckV2Base):

    def check(self, instance):
        # type: (_InstanceType) -> Optional[CheckError]
        raise NotImplementedError


class StatefulAgentCheck(Stateful, AgentCheckV2):
    def check(self, instance):
        # type: (_InstanceType) -> Optional[CheckError]

        self.setup()
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


class TransactionalAgentCheck(Transactional, AgentCheckV2):
    def check(self, instance):
        # type: (_InstanceType) -> Optional[CheckError]

        self.setup()

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
