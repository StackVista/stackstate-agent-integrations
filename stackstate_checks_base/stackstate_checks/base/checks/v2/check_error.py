

class CheckError(Exception):
    """
    Agent error that needs to be converted to Critical Service Check
    """

    def to_string(self):
        # type: () -> str
        return "check error: {}".format(self.message)
