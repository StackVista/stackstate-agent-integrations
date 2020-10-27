# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.base import AgentCheck

import logging
import os

try:
    import cPickle as pickle
except ImportError:
    # python 3 support as pickle module
    import pickle

log = logging.getLogger(__name__)

# get the agent configuration(/etc/stackstate-agent/conf.d) folder path
AGENT_CONFD_PATH = AgentCheck.get_agent_confd_path()
# Full path of state file
DYNATRACE_STATE_FILE = os.path.join(AGENT_CONFD_PATH, "/dynatrace_event.d/dynatrace_event_state.pickle")


class DynatraceEventState(object):
    """
    A class to keep the state of the events coming from Dynatrace. The structure of state looks like below:

    # timestamp   : last event processed timestamp
    # entityId    : EntityId of Dynatrace for which event occured
    # event_type  : Event Type of an event for the EntityId
    # event       : Event details for the EntityId

    state = {
                "url": {
                        "lastProcessedEventTimestamp": timestamp,
                        "events": {
                                    "entityId": {
                                                    "event_type": event
                                                }
                                  }
                        }
            }

    """
    def __init__(self):
        self.data = dict()

    def persist(self):
        try:
            log.debug("Persisting status to %s" % DYNATRACE_STATE_FILE)
            f = open(DYNATRACE_STATE_FILE, 'wb+')
            try:
                pickle.dump(self, f)
            finally:
                f.close()
        except Exception as e:
            log.exception("Error persisting the data: {}".format(str(e)))
            raise e

    def clear(self, instance):
        """
        Clear the instance state as it can have multiple instance state
        :param instance: the instance for which state need to be cleared
        :return: None
        """
        if instance in self.data:
            del self.data[instance]
        else:
            log.debug("There is no state existing for the instance {}".format(instance))

    @classmethod
    def load_latest_state(cls):
        try:
            if not os.path.exists(DYNATRACE_STATE_FILE):
                return None
            f = open(DYNATRACE_STATE_FILE, 'rb')
            try:
                r = pickle.load(f)
                return r
            except Exception as e:
                log.exception("Error loading the state : {}".format(str(e)))
            finally:
                f.close()
        except (IOError, EOFError) as e:
            raise e
