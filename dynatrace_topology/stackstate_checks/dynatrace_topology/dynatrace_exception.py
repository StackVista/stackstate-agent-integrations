# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)


class DynatraceError(Exception):
    """
    Exception raised for errors in Dynatrace API endpoint response

    Attributes:
        message         -- explanation of the error response
        code            -- status code of the error response
        component_type  -- Type of the component for which error occured
    """

    def __init__(self, message, code, component_type):
        super(DynatraceError, self).__init__(self.message)
        self.message = message
        self.code = code
        self.component_type = component_type

    def __str__(self):
        return 'Got an unexpected error with status code {0} and message {1} while processing {2} component ' \
               'type'.format(self.code, self.message, self.component_type)
