# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from schematics.models import Model
from schematics.types import StringType, ListType, DictType, PolyModelType, IntType


# Allow copy.deepcopy to work on the schematic models
class PickleModel(Model):
    def __getstate__(self):
        return self.to_native()

    def __setstate__(self, kwargs):
        self.__init__(kwargs)


class SplunkConfigSavedSearch(PickleModel):
    name = StringType(required=True)
    parameters = DictType(StringType, required=True)
    max_query_chunk_seconds = IntType()
    unique_key_fields = ListType(StringType)


class SplunkConfigBasicAuthStructure(PickleModel):
    username = StringType(required=True)
    password = StringType(required=True)


class SplunkConfigBasicAuth(PickleModel):
    basic_auth = PolyModelType(SplunkConfigBasicAuthStructure, required=True)


class SplunkConfigInstance(PickleModel):
    url = StringType(required=True)
    authentication = PolyModelType([SplunkConfigBasicAuth], required=True)
    saved_searches = ListType(PolyModelType(SplunkConfigSavedSearch), required=True)
    tags = ListType(StringType, required=True)


class SplunkInitConfig(PickleModel):
    default_restart_history_time_seconds = IntType()
    default_max_query_chunk_seconds = IntType()
    unique_key_fields = ListType(StringType)


class SplunkConfig(PickleModel):
    init_config = PolyModelType(SplunkInitConfig)
    instances = ListType(PolyModelType(SplunkConfigInstance), required=True)
