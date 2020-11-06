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
            except IOError:
                # log info
                return
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

        self.data[instance.instance_key] = data

    def flush(self, instance):
        """

        """
        if instance.instance_key in self.data:
            with open(instance.file_location, 'w') as f:
                f.write(self.data[instance.instance_key])
