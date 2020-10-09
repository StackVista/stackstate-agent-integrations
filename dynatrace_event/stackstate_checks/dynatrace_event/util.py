import cPickle as pickle
import logging
import os
import pwd

log = logging.getLogger(__name__)

# Temporary directory for creating the state file
PATH = "/etc/stackstate-agent/conf.d/dynatrace_event.d/"
# Full path of temporary file
pickle_path = os.path.join(PATH, "dynatrace_data" + '.pickle')
# get the user details of stackstate-agent
user = pwd.getpwnam('stackstate-agent')


class DynatraceStatus:

    def __init__(self):
        pass

    def persist(self):
        try:
            log.debug("Persisting status to %s" % pickle_path)
            f = open(pickle_path, 'w+')
            # Change the ownership of the file, so it could be read with stackstate-agent user
            os.chown(pickle_path, user.pw_uid, user.pw_gid)
            try:
                pickle.dump(self, f)
            finally:
                f.close()
        except Exception as e:
            log.exception("Error persisting the data: {}".format(str(e)))

    @classmethod
    def load_latest_status(cls):
        try:
            f = open(pickle_path)
            try:
                r = pickle.load(f)
                return r
            finally:
                f.close()
        except (IOError, EOFError):
            return None


class DynatraceData(DynatraceStatus):

    def __init__(self):
        DynatraceStatus.__init__(self)
        self.data = dict()
