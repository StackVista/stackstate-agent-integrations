from schematics import Model
from typing import Any, Dict, TypeVar

InstanceType = TypeVar('InstanceType', Model, Dict[str, Any])
StateType = TypeVar('StateType', Model, Dict[str, Any])


class CheckResponse(object):
    """
    CheckResponse is the return type of the check function of Agent V2 checks
    """
    def __init__(self, *args, **kwargs):
        self.check_error = kwargs.get('check_error')  # type: Exception
        self.persistent_state = kwargs.get('persistent_state')  # type: StateType
        self.transactional_state = kwargs.get('transactional_state')  # type: StateType
