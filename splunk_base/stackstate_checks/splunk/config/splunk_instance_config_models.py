# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.base.utils.validations_utils import ForgivingBaseModel, StrictBaseModel
from typing import List, Optional


class SplunkConfigSavedSearchDefault(ForgivingBaseModel):
    name: Optional[str] = None
    match: Optional[str] = None
    parameters: Optional[dict] = None
    request_timeout_seconds: Optional[int] = None
    search_max_retry_count: Optional[int] = None
    search_seconds_between_retries: Optional[int] = None
    max_initial_history_seconds: int = 86400
    max_query_chunk_seconds: int = 300
    unique_key_fields: List[str] = ["_bkt", "_cd"]
    app: Optional[str] = None
    batch_size: Optional[int] = None
    initial_history_time_seconds: int = 0
    max_restart_history_seconds: int = 86400
    max_query_time_range: int = 3600
    initial_delay_seconds: int = 0
    metric_name: Optional[str] = None
    metric_name_field: Optional[str] = None
    metric_value_field: Optional[str] = None


class SplunkConfigTokenAuthStructure(StrictBaseModel):
    name: str
    audience: str
    initial_token: str
    token_expiration_days: int = 90
    renewal_days: int = 10


class SplunkConfigBasicAuthStructure(StrictBaseModel):
    username: str
    password: str


class SplunkConfigAuthentication(StrictBaseModel):
    token_auth: Optional[SplunkConfigTokenAuthStructure] = None
    basic_auth: Optional[SplunkConfigBasicAuthStructure] = None


class SplunkConfigInstance(ForgivingBaseModel):
    url: str
    tags: List[str] = []
    authentication: SplunkConfigAuthentication
    saved_searches_parallel: int = 3
    ignore_saved_search_errors: bool = False
    saved_searches: List[SplunkConfigSavedSearchDefault] = []
    verify_ssl_certificate: Optional[bool] = None


class SplunkConfig(ForgivingBaseModel):
    init_config: dict
    instances: List[SplunkConfigInstance]
