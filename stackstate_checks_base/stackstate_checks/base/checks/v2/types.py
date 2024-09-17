from stackstate_checks.base.utils.validations_utils import StrictBaseModel
from typing import Any, Dict, TypeVar, Optional

InstanceType = TypeVar('InstanceType', StrictBaseModel, Dict[str, Any])
StateType = TypeVar('StateType', StrictBaseModel, Dict[str, Any])


class CheckResponse(object):
    """
    CheckResponse is the return type of the check function of Agent V2 checks
    """
    def __init__(self, check_error=None, persistent_state=None, transactional_state=None):
        # type: (Optional[Exception], Optional[StateType], Optional[StateType]) -> None
        self.check_error = check_error
        self.persistent_state = persistent_state
        self.transactional_state = transactional_state
