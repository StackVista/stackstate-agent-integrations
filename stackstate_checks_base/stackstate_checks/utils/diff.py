import difflib
import json
from datetime import datetime, date


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def compute_diff(computed_dict, expected_filepath):
    current_data = json.dumps(computed_dict, sort_keys=True, default=json_serial, indent=2)
    with open(expected_filepath) as f:
        expected_data = json.dumps(f.read(), sort_keys=True, default=json_serial, indent=2)
        # expected_data = f.read()
        delta = difflib.unified_diff(
            a=expected_data.strip().splitlines(),
            b=current_data.strip().splitlines()
        )
        return ''.join(delta)


def delta(a_json, another_json):
    a = json.dumps(a_json, sort_keys=True, default=json_serial, indent=2)
    b = json.dumps(another_json, sort_keys=True, default=json_serial, indent=2)
    delta = difflib.unified_diff(
        a=a.strip().splitlines(keepends=True),
        b=b.strip().splitlines(keepends=True)
    )
    return ''.join(delta)
