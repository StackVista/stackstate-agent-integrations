from schematics import Model
from schematics.types import StringType, ListType, ModelType, DictType

class SoftwareTechnology(Model):
    type = StringType()

class QueueProperties(Model):
    awsNameTag = StringType()
    boshName = StringType()
    conditionalName = StringType()
    customizedName = StringType()
    detectedName = StringType()
    dt_security_context = ListType(StringType())
    gcpZone = StringType()
    oneAgentCustomHostName = StringType()
    queueDestinationType = StringType()
    queueName = StringType()
    queueVendorName = StringType()
    softwareTechnologies = ListType(ModelType(SoftwareTechnology))

class Relationship(Model):
    id = StringType()
    type = StringType()

class QueueEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(QueueProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})