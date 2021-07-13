# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from six import string_types
from schematics.types import StringType, BaseType
from schematics.exceptions import ValidationError


class StrictStringType(StringType):
    def __init__(self, value_mapping=None, accept_empty=True, **kwargs):
        self.value_mapping = value_mapping
        self.accept_empty = accept_empty
        super(StrictStringType, self).__init__(**kwargs)

    def convert(self, value, context=None):
        # check if this is a string or bytes which is converted to string in super.convert()
        if not isinstance(value, (string_types, bytes)):
            raise ValidationError('Value must be a string')

        # strict string types expects a value, not None or ''
        if not self.accept_empty and not value:
            raise ValidationError('Value must not be a empty string')

        value = super(StrictStringType, self).convert(value, context)
        if value is None:
            return self.default()

        if self.value_mapping:
            value = self.value_mapping(value)

        return value


class ClassType(BaseType):
    def __init__(self, expected_class, **kwargs):
        self.expected_class = expected_class
        super(ClassType, self).__init__(**kwargs)

    def convert(self, value, context=None):
        # check if the value is of the expected class
        if not isinstance(value, self.expected_class):
            raise ValidationError("Value must be of class: %s" % str(self.expected_class))

        return value
