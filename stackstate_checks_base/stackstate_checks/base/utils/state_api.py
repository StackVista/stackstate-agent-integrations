import logging

try:
    import state

    using_stub_state = False
except ImportError:
    from ..stubs import state

    using_stub_state = True


class StateApi(object):
    def __init__(self, check):
        self.check = check
        self.log = logging.getLogger('{}.{}'.format(__name__, self.check.name))
        if using_stub_state:
            self.log.warning("Using stub state api")

    def get_state(self, key):
        state.get_state(self.check, self.check.check_id, key)

    def set_state(self, key, new_state):
        state.set_state(self.check, self.check.check_id, key, new_state)
