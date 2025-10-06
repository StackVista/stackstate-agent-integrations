# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

"""
Common Dynatrace constants and helpers shared across checks.
"""

# Entity ID prefixes that we materialize as components in StackState
SUPPORTED_ENTITY_ID_PREFIXES = (
    'HOST-',
    'PROCESS_GROUP-',
    'PROCESS_GROUP_INSTANCE-',
    'SERVICE-',
    'APPLICATION-',
    'CUSTOM_DEVICE-',
    'QUEUE-',
    'SYNTHETIC_TEST-',
)

SUPPORTED_ENTITY_TYPES_PARAM_SELECTORS = (
    'type("PROCESS_GROUP_INSTANCE")',
    'type("HOST")',
    'type("APPLICATION")',
    'type("PROCESS_GROUP")',
    'type("SERVICE")',
    'type("CUSTOM_DEVICE")',
    'type("QUEUE")',
    'type("SYNTHETIC_TEST")',
)



def is_supported_entity_id(entity_id: str) -> bool:
    """Return True if the id starts with a supported component prefix."""
    if not isinstance(entity_id, str):
        return False
    return any(entity_id.startswith(prefix) for prefix in SUPPORTED_ENTITY_ID_PREFIXES)
