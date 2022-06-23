

class CheckError(Exception):
    """
    Check error is a wrapper around exceptions that occur in Agent Checks that is returned as an Optional[CheckError]
    in Agent check functions.
    """

    def to_string(self):  # type: () -> str
        """
        to_string returns a string representation of the Exception.
        @return: string representing the underlying exception.
        """
        return "check error: {}".format(self.message)
