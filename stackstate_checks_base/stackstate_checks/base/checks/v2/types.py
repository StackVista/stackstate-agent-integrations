from stackstate_checks.base.utils.validations_utils import CheckBaseModel
from typing import Any, Dict, TypeVar, Optional

InstanceType = TypeVar('InstanceType', CheckBaseModel, Dict[str, Any])
StateType = TypeVar('StateType', CheckBaseModel, Dict[str, Any])


class CheckResponse(object):
    """
    CheckResponse is the return type of the check function of Agent V2 checks
    """
    def __init__(self, check_error=None, persistent_state=None, transactional_state=None):
        # type: (Optional[Exception], Optional[StateType], Optional[StateType]) -> None
        self.check_error = check_error
        self.persistent_state = persistent_state
        self.transactional_state = transactional_state
