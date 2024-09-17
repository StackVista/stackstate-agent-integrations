from typing import Union, Dict, Any
from pydantic import ValidationError
from .common import sanitize_url_as_valid_filename
import json

from pydantic import BaseModel


def generate_state_key(instance_url, key):
    # type: (str, str) -> str
    """
    State key is used for a filename of the file where state is stored.
    It is constructed from sanitized `TopologyInstance.url` and provided key.
    """
    return "{}_{}".format(sanitize_url_as_valid_filename(instance_url), key)


def validate_state(new_state):
    # type (Union[Dict[str, Any], Model]) -> Dict
    if isinstance(new_state, dict):
        pass
    # check to see if this state has a Schematics schema, validate it to make sure it meets the schema and return
    # the primitive (dict)
    elif isinstance(new_state, BaseModel):
        new_state = new_state.dict()
    else:
        raise ValidationError(
            "Got unexpected {} for new state, expected dictionary or schematics.Model".format(type(new_state))
        )

    return json.dumps(new_state)
