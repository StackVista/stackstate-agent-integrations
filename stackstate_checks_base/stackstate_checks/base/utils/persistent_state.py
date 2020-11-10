# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import os
import json
from schematics.models import Model


class PersistentInstance:
    """
    PersistentInstance is used to describe an instance of state that is persisted to disk
    """
    def __init__(self, instance_key, file_location):
        """
        `instance_key` is the unique identifier for an instance of an integration that is used to uniquely identify
        the state
        `file_location` is the location on disk where the state file is store
        """
        self.instance_key = instance_key
        self.file_location = file_location


class PersistentState:
    """
    PersistentState stores data onto disk for the given persistence instance.
    It stores the state directly onto disk the first time data is written into the state, thereafter only updating the
    in-memory state and writing to disk once `flush` is called. This reduces the io operation for frequently updated
    state.
    """

    def __init__(self, logger):
        """
        `logger` the logger that is used to log messages
        """
        self.state = dict()
        self.log = logger

    def clear(self, instance):
        """
        clear removes the state for this instance from the in-memory state, as well as the state file from disk.
        `instance` the instance for which the clear operation is performed.
        """
        if instance.instance_key in self.state:
            del self.state[instance.instance_key]

            try:
                os.remove(instance.file_location)
            except OSError as e:
                self.log.error("PersistentState: Failed to remove state file for instance: {}. {}"
                               .format(instance.instance_key, e))
                pass

            self.log.debug("PersistentState: Removed state for instance: {}".format(instance.instance_key))

    def get_state(self, instance, schema=None):
        """
        get_state returns the state for a given instance, if a schema is specified it's validated and returned in that
        schema
        `instance` the persistence instance to retrieve the state for.
        `schema` a optional schematics schema to which the stored state is validated and returned
        """
        if instance.instance_key not in self.state:
            try:
                with open(instance.file_location, 'r') as f:
                    state = json.loads(f.read())
            except ValueError as e:
                self.log.error("PersistentState: State file is corrupted for instance: {} stored at: {}. {}"
                               .format(instance.instance_key, instance.file_location, e))
                raise StateCorruptedException(e)
            except IOError as e:
                self.log.error("PersistentState: Error occurred while retrieving state file for instance: {} "
                               "stored at: {}. {}"
                               .format(instance.instance_key, instance.file_location, e))
                raise StateReadException(e)
        else:
            state = json.loads(self.state[instance.instance_key])

        if schema:
            state = schema(state)
            state.validate()

        return state

    def set_state(self, instance, state):
        """
        set_state stores the given state for this instance into the persistent state. If this is the first insertion,
        the state is flushed to disk to validate the instance file_location and writing permissions for this instance.
        `instance` the persistence instance to set the state for.
        `state` the state which will be saved in memory and file.
        """
        if isinstance(state, dict):
            state = json.dumps(state)
        elif isinstance(state, Model):
            state = json.dumps(state.to_native())

        # first time insert for this instance, flush right away to ensure that we can write to file
        if instance.instance_key not in self.state:
            self.state[instance.instance_key] = state
            self.flush(instance)
        else:
            self.state[instance.instance_key] = state

    def flush(self, instance):
        """
        flush writes the state data for this instance to disk
        `instance` the persistence instance for which the state is flushed to disk.
        """
        if instance.instance_key in self.state:
            try:
                with open(instance.file_location, 'w') as f:
                    f.write(self.state[instance.instance_key])
            except IOError as e:
                # if we couldn't save, drop the state
                del self.state[instance.instance_key]
                raise StateNotPersistedException(e)


class StateNotPersistedException(Exception):
    """
    StateNotPersistedException
    """
    pass


class StateCorruptedException(Exception):
    """
    StateCorruptedException
    """
    pass


class StateReadException(Exception):
    """
    StateReadException
    """
    pass
