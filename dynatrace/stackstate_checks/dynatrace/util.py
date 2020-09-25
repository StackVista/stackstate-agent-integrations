import cPickle as pickle
import logging
import os
from stackstate_checks.base import AgentCheck

PATH = "/etc/stackstate-agent/conf.d/dynatrace.d/"
log = logging.getLogger(__name__)

pickle_path = os.path.join(PATH, "dynatrace_data" + '.pickle')


class DynatraceStatus:

    def __init__(self):
        pass

    def persist(self):
        try:
            log.debug("Persisting status to %s" % PATH)
            f = open(PATH, 'w+')
            try:
                pickle.dump(self, f)
            finally:
                f.close()
        except Exception as e:
            log.exception("Error persisting the data: {}".format(str(e)))

    @classmethod
    def load_latest_status(cls):
        try:
            f = open(PATH)
            try:
                r = pickle.load(f)
                return r
            finally:
                f.close()
        except (IOError, EOFError):
            return None

    # def to_dict(self):
    #     return {}


class DynatraceData(DynatraceStatus):

    def __init__(self, url):
        DynatraceStatus.__init__(self)
        self.data = dict()

    # def to_dict(self):
    #     status_info = DynatraceStatus.to_dict(self)
    #     status_info.update({
    #         'data': self.data
    #     })
    #     return status_info
