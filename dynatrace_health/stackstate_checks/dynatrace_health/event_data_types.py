from typing import List, Any, Optional
from stackstate_checks.base.utils.validations_utils import ForgivingBaseModel


class PropertyEntry(ForgivingBaseModel):
    key: str
    value: Optional[str] = None  # Make optional since some properties might not have values


class Reference(ForgivingBaseModel):
    id: str
    type: Optional[str] = None  # Make optional since some references might not have a type


class EntityId(ForgivingBaseModel):
    entityId: Reference
    name: Optional[str] = None  # Make optional since some entity IDs might not have a name


class DynatraceEvent(ForgivingBaseModel):
    eventId: str
    startTime: int
    endTime: Optional[int] = None  # Make optional since some events might not have a valid end time
    eventType: str
    title: Optional[str] = None  # Make optional since some events might have empty titles
    entityId: EntityId
    properties: Optional[List[PropertyEntry]] = None  # Make optional since some events might not have properties
    status: str
    correlationId: Optional[str] = None  # Make this optional since some API responses don't include it
    entityTags: Optional[List[Any]] = None  # Make optional
    managementZones: Optional[List[Any]] = None  # Make optional
    underMaintenance: Optional[bool] = False  # Make optional with default
    suppressAlert: Optional[bool] = False  # Make optional with default
    suppressProblem: Optional[bool] = False  # Make optional with default
    frequentEvent: Optional[bool] = False  # Make optional with default


class EventsResponse(ForgivingBaseModel):
    totalCount: Optional[int] = None  # Make optional since some responses might not have this
    pageSize: Optional[int] = None  # Make optional since some responses might not have this
    events: List[DynatraceEvent]
    warnings: Optional[List[Any]] = None  # Make optional since some responses might not have warnings
