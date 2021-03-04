import json
import os

from six import PY3


def read_file(filename):
    with open(get_path_to_file(filename), "r") as f:
        return f.read() if PY3 else f.read().decode("utf-8")


def load_json_from_file(filename):
    raw_json_file = read_file(filename)
    return json.loads(raw_json_file)


def get_path_to_file(filename):
    path_to_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', filename)
    return path_to_file
