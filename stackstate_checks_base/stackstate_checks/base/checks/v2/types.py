from schematics import Model
from typing import Any, Dict, TypeVar

InstanceType = TypeVar('InstanceType', Model, Dict[str, Any])
StateType = TypeVar('StateType', Model, Dict[str, Any])
