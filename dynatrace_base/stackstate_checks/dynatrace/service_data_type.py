from schematics import Model
from schematics.types import IntType, StringType, ListType, BooleanType, ModelType, DictType

class SoftwareTechnology(Model):
    type = StringType()

class ServiceProperties(Model):
    agentTechnologyType = StringType(choices=["TECH_TYPE_1", "TECH_TYPE_2"])  # Sample Enum
    akkaActorSystem = StringType()
    applicationBuildVersion = ListType(StringType())
    applicationEnvironment = ListType(StringType())
    applicationName = ListType(StringType())
    applicationReleaseVersion = ListType(StringType())
    awsNameTag = StringType()
    boshName = StringType()
    className = StringType()
    cloudDatabaseProvider = StringType(choices=["PROVIDER_1", "PROVIDER_2"])  # Sample Enum
    conditionalName = StringType()
    contextRoot = StringType()
    customizedName = StringType()
    databaseHostNames = ListType(StringType())
    databaseName = StringType()
    databaseVendor = StringType()
    detectedName = StringType()
    dt_security_context = ListType(StringType())
    esbApplicationName = StringType()
    gcpZone = StringType()
    ibmCtgGatewayUrl = StringType()
    ibmCtgServerName = StringType()
    ipAddress = ListType(StringType())
    isExternalService = BooleanType()
    oneAgentCustomHostName = StringType()
    path = StringType()
    port = IntType()
    publicCloudId = StringType()
    publicCloudRegion = StringType()
    publicDomainName = StringType()
    remoteEndpoint = StringType()
    remoteServiceName = StringType()
    serviceDetectionAttributes = DictType(StringType)
    serviceTechnologyTypes = ListType(StringType())
    serviceType = StringType(choices=["SERVICE_TYPE_1", "SERVICE_TYPE_2"])  # Sample Enum
    softwareTechnologies = ListType(ModelType(SoftwareTechnology))
    unifiedServiceIndicators = ListType(StringType())
    webApplicationId = StringType()
    webServerName = StringType()
    webServiceName = StringType()
    webServiceNamespace = StringType()

class Relationship(Model):
    id = StringType()
    type = StringType()

class ServiceEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(ServiceProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})