# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import os
import json
import errno
from schematics import Model
from .schemas import StrictStringType


class StateDescriptorSchema(Model):
    """
    StateDescriptorSchema is used to validate data passed to the StateDescriptor
    """
    instance_key = StrictStringType(required=True, accept_empty=False)
    file_location = StrictStringType(required=True, accept_empty=False)


class StateDescriptor:
    """
    StateDescriptor is used to describe an instance of state that is persisted to disk
    """
    def __init__(self, instance_key, check_conf_d_path):
        """
        `instance_key` is the unique identifier for an instance of an integration that is used to uniquely identify
        the state
        `file_location` is the location on disk where the state file is store
        """
        _file_location = "{}.state".format(os.path.join(check_conf_d_path, instance_key))
        StateDescriptorSchema({'instance_key': instance_key, 'file_location': _file_location}).validate()
        self.instance_key = instance_key
        self.file_location = _file_location


class StateManager:
    """
    StateManager stores data onto disk for the given persistence instance.
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
            self.log.debug("PersistentState: Removed state for instance: {}".format(instance.instance_key))
        except OSError as e:
            # File not found / no file for this state so the state doesn't exist. Catch exception and return None
            if e.errno == errno.ENOENT:
                self.log.debug("PersistentState: No state file found for instance: {} expecting it at: {}. {}"
                               .format(instance.instance_key, instance.file_location, e))
                return None

            self.log.error("PersistentState: Failed to remove state file for instance: {}. {}"
                           .format(instance.instance_key, e))
            raise StateClearException(e)


    def _read_state(self, instance):
        """
        read_state reads state from the instance.file_location and loads it as json
        """
        try:
            with open(instance.file_location, 'r') as f:
                state = json.loads(f.read())
                self.state[instance.instance_key] = state
                return state
        except ValueError as e:
            self.log.error("PersistentState: State file is corrupted for instance: {} stored at: {}. {}"
                           .format(instance.instance_key, instance.file_location, e))
            raise StateCorruptedException(e)
        except IOError as e:
            # File not found / no file for this state so the state doesn't exist. Catch exception and return None
            if e.errno == errno.ENOENT or e.errno == errno.EINVAL:
                self.log.debug("PersistentState: No state file found for instance: {}"
                               .format(instance.instance_key))
                return None

            self.log.error("PersistentState: Error occurred while retrieving state file for instance: {} "
                           "stored at: {}. {}"
                           .format(instance.instance_key, instance.file_location, e))
            raise StateReadException(e)

    def get_state(self, instance, schema=None):
        """
        get_state returns the state for a given instance, if a schema is specified it's validated and returned in that
        schema
        `instance` the persistence instance to retrieve the state for.
        `schema` a optional schematics schema to which the stored state is validated and returned
        """
        if instance.instance_key not in self.state:
            state = self._read_state(instance)
        else:
            state = self.state[instance.instance_key]

        if state and schema:
            state = schema(state)
            state.validate()

        return state

    def set_state(self, instance, state, flush=True):
        """
        set_state stores the given state for this instance into the persistent state. If this is the first insertion,
        the state is flushed to disk to validate the instance file_location and writing permissions for this instance.
        `instance` the persistence instance to set the state for.
        `state` the state which will be saved in memory and file.
        `flush` this toggles whether the state is written to disk immediately, if True it flushes.
        """
        if isinstance(state, dict):
            pass
        elif isinstance(state, Model):
            state = state.to_primitive()
        elif state is None:
            return self.clear(instance)
        else:
            raise ValueError("Got unexpected {} for argument state, expected dictionary or "
                             "schematics.Model"
                             .format(type(state)))

        self.state[instance.instance_key] = state

        if flush:
            self.flush(instance)

    def flush(self, instance):
        """
        flush writes the state data for this instance to disk
        `instance` the persistence instance for which the state is flushed to disk.
        """
        if instance.instance_key in self.state:
            # check if folder and file exists before writing
            try:
                if not os.path.exists(os.path.dirname(instance.file_location)):
                    os.makedirs(os.path.dirname(instance.file_location))

                with open(instance.file_location, 'w+') as f:
                    f.write(json.dumps(self.state[instance.instance_key]))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    # if we couldn't save, log the state
                    self.log.error('PersistentState: Could not persist state for instance: {} at {}, '
                                   'continuing with state: {}. '
                                   'In an event of agent failure, replace the state file with this state.'
                                   .format(instance.instance_key, instance.file_location,
                                           self.state[instance.instance_key]))
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


class StateClearException(Exception):
    """
    StateClearException
    """
    pass
