# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import os
import json
from schematics.models import Model


class PersistentInstance:
    def __init__(self, instance_key, file_location):
        self.instance_key = instance_key
        self.file_location = file_location


class PersistentState:
    """

    """

    def __init__(self):
        self.data = dict()

    def clear(self, instance):
        """

        """
        if instance.instance_key in self.data:
            del self.data[instance.instance_key]

        try:
            os.remove(instance.file_location)
        except OSError:
            # log info
            pass

    def get_state(self, instance, schema=None):
        """

        """
        if instance.instance_key not in self.data:
            try:
                with open(instance.file_location, 'r') as f:
                    data = json.loads(f.read())
            except ValueError as e:
                # log this
                raise StateCorruptedException(e)
            except IOError as e:
                # log info
                raise StateReadException(e)
        else:
            data = json.loads(self.data[instance.instance_key])

        if schema:
            data = schema(data)
            data.validate()

        return data

    def set_state(self, instance, data):
        """

        """
        if isinstance(data, dict):
            data = json.dumps(data)
        elif isinstance(data, Model):
            data = json.dumps(data.to_native())

        # first time insert for this instance, flush right away to ensure that we can write to file
        if instance.instance_key not in self.data:
            self.data[instance.instance_key] = data
            self.flush(instance)
        else:
            self.data[instance.instance_key] = data

    def flush(self, instance):
        """

        """
        if instance.instance_key in self.data:
            try:
                with open(instance.file_location, 'w') as f:
                    f.write(self.data[instance.instance_key])
            except IOError as e:
                # if we couldn't save, drop the state
                del self.data[instance.instance_key]
                raise StateNotPersistedException(e)


class StateNotPersistedException(Exception):
    pass


class StateCorruptedException(Exception):
    pass


class StateReadException(Exception):
    pass
