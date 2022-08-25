# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from schematics.models import Model
from schematics.types import StringType, ListType, DictType, PolyModelType, IntType, BooleanType, BaseType, ModelType


# Allow copy.deepcopy to work on the schematic models
class PickleModel(Model):
    def __getstate__(self):
        return self.to_native()

    def __setstate__(self, kwargs):
        self.__init__(kwargs)


class SplunkConfigSavedSearchDefault(PickleModel):
    name = StringType(default=None)
    match = StringType(default=None)
    parameters = DictType(BaseType, default={"force_dispatch": True, "dispatch.now": True})
    request_timeout_seconds = IntType(default=5)
    search_max_retry_count = IntType(default=3)
    search_seconds_between_retries = IntType(default=1)
    verify_ssl_certificate = BooleanType(default=False)
    max_initial_history_seconds = IntType(default=86400)
    max_query_chunk_seconds = IntType(default=300)
    unique_key_fields = ListType(StringType, default=["_bkt", "_cd"])
    app = StringType(default="search")
    batch_size = IntType(default=1000)
    saved_searches_parallel = IntType(default=3)
    initial_history_time_seconds = IntType(default=0)
    max_restart_history_seconds = IntType(default=86400)
    max_query_time_range = IntType(default=3600)
    initial_delay_seconds = IntType(default=0)


class SplunkConfigSavedSearchAlternativeFields(SplunkConfigSavedSearchDefault):
    metric_name_field = StringType()
    metric_value_field = StringType()


class SplunkConfigSavedSearchAlternativeFields2(SplunkConfigSavedSearchDefault):
    metric_name = StringType()
    metric_value_field = StringType()


class SplunkConfigTokenAuthStructure(PickleModel):
    name = StringType()
    audience = StringType()
    initial_token = StringType(required=True)
    renewal_days = IntType(required=True)


class SplunkConfigBasicAuthStructure(PickleModel):
    username = StringType(required=True)
    password = StringType(required=True)


class SplunkConfigAuthentication(PickleModel):
    token_auth = ModelType(SplunkConfigTokenAuthStructure)
    basic_auth = ModelType(SplunkConfigBasicAuthStructure)


class SplunkConfigInstance(PickleModel):
    url = StringType(required=True)
    tags = ListType(StringType, required=True)
    authentication = ModelType(SplunkConfigAuthentication, required=True)
    saved_searches_parallel = IntType(default=3)
    ignore_saved_search_errors = BooleanType(default=False)
    saved_searches = ListType(PolyModelType([SplunkConfigSavedSearchDefault, SplunkConfigSavedSearchAlternativeFields,
                                             SplunkConfigSavedSearchAlternativeFields2]), required=True)


class SplunkConfig(PickleModel):
    init_config = DictType(BaseType)
    instances = ListType(ModelType(SplunkConfigInstance), required=True)
