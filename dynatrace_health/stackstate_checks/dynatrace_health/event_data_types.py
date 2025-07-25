from typing import List, Any
from stackstate_checks.base.utils.validations_utils import ForgivingBaseModel


class PropertyEntry(ForgivingBaseModel):
    key: str
    value: str


class Reference(ForgivingBaseModel):
    id: str
    type: str


class EntityId(ForgivingBaseModel):
    entityId: Reference
    name: str


class DynatraceEvent(ForgivingBaseModel):
    eventId: str
    startTime: int
    endTime: int
    eventType: str
    title: str
    entityId: EntityId
    properties: List[PropertyEntry]
    status: str
    correlationId: str
    entityTags: List[Any]
    managementZones: List[Any]
    underMaintenance: bool
    suppressAlert: bool
    suppressProblem: bool
    frequentEvent: bool


class EventsResponse(ForgivingBaseModel):
    totalCount: int
    pageSize: int
    events: List[DynatraceEvent]
    warnings: List[Any]
