from schematics import Model
from schematics.types import StringType, IntType, BooleanType, ListType, DictType, ModelType


# Extra classes for reused structures
class SoftwareTechnology(Model):
    type = StringType()


class Relationship(Model):
    id = StringType()
    type = StringType()


class LogPathEntry(Model):
    key = StringType()
    value = IntType()

class LogFileStatusEntry(Model):
    key = StringType(required=True)  # Assuming 'key' is always required
    value = StringType(required=True)  # Assuming 'value' is always required

class LogFileStatus(Model):
    logFileStatus = ListType(ModelType(LogFileStatusEntry), default=[])

class StorageStatus(Model):
    storageStatus = StringType(required=True)  # Assuming 'storageStatus' is always required

class LogSourceStateEntry(Model):
    key = StringType(required=True)  # Assuming 'key' is always required
    value = ModelType(StorageStatus, required=True)  # Assuming 'value' is always required

class LogSourceState(Model):
    logSourceState = ListType(ModelType(LogSourceStateEntry), default=[])

class ApplicationProperties(Model):
    applicationInjectionType = StringType()
    applicationMatchTarget = StringType()
    applicationType = StringType()
    awsNameTag = StringType()
    boshName = StringType()
    conditionalName = StringType()
    customizedName = StringType()
    detectedName = StringType()
    dt_security_context = ListType(StringType())
    gcpZone = StringType()
    oneAgentCustomHostName = StringType()
    ruleAppliedMatchType = StringType()
    ruleAppliedPattern = StringType()


class CustomDeviceProperties(Model):
    arn = StringType()
    awsNameTag = StringType()
    boshName = StringType()
    conditionalName = StringType()
    customFavicon = StringType()
    customProperties = DictType(StringType)
    customizedName = StringType()
    detectedName = StringType()
    dnsNames = ListType(StringType())
    dt_security_context = ListType(StringType())
    gcpZone = StringType()
    ipAddress = ListType(StringType())
    listenPorts = ListType(StringType())
    oneAgentCustomHostName = StringType()


class HostProperties(Model):
    additionalSystemInfo = ListType(DictType(StringType))
    autoInjection = StringType()
    awsNameTag = StringType()
    azureComputeModeName = StringType()
    azureEnvironment = StringType()
    azureHostNames = ListType(StringType())
    azureResourceGroupName = StringType()
    azureSiteNames = ListType(StringType())
    azureSku = StringType()
    azureVmScaleSetName = StringType()
    azureVmSizeLabel = StringType()
    azureZone = StringType()
    bitness = StringType()
    boshAvailabilityZone = StringType()
    boshDeploymentId = StringType()
    boshInstanceId = StringType()
    boshInstanceName = StringType()
    boshName = StringType()
    boshStemcellVersion = StringType()
    cloudPlatformVendorVersion = StringType()
    cloudType = StringType()
    conditionalName = StringType()
    cpuCores = IntType()
    customHostMetadata = DictType(StringType)
    customizedName = StringType()
    detectedName = StringType()
    dnsNames = ListType(StringType())
    dt_security_context = ListType(StringType())
    ebpfDiscoveryMonitored = BooleanType()
    ebpfHasPublicTraffic = BooleanType()
    gceHostName = StringType()
    gceInstanceId = StringType()
    gceInstanceName = StringType()
    gceMachineType = StringType()
    gceNumericProjectId = StringType()
    gceProjectId = StringType()
    gcePublicIpAddresses = ListType(StringType())
    gcpZone = StringType()
    hasPublicTraffic = BooleanType()
    hostGroupName = StringType()
    hypervisorType = StringType()
    installerPotentialProblem = BooleanType()
    installerSupportAlert = BooleanType()
    installerTrackedDownload = BooleanType()
    installerVersion = StringType()
    ipAddress = ListType(StringType())
    isMonitoringCandidate = BooleanType()
    kubernetesLabels = DictType(StringType)
    logFileStatus = ModelType(LogFileStatus)
    logPathLastUpdate = LogPathEntry()
    logSourceState = ModelType(LogSourceState)
    logicalCpuCores = IntType()
    logicalCpus = IntType()
    macAddresses = ListType(StringType())
    memoryTotal = IntType()
    monitoringMode = StringType()
    networkZone = StringType()
    oneAgentCustomHostName = StringType()
    osArchitecture = StringType()
    osServices = ListType(StringType())
    osType = StringType()
    osVersion = StringType()
    paasMemoryLimit = IntType()
    paasVendorType = StringType()
    physicalMemory = IntType()
    simultaneousMultithreading = IntType()
    softwareTechnologies = ListType(ModelType(SoftwareTechnology))
    standalone = BooleanType()
    standaloneSpecialAgentsOnly = BooleanType()
    state = StringType()
    virtualCpus = IntType()
    zosCPUModelNumber = StringType()
    zosCPUSerialNumber = StringType()
    zosLparName = StringType()
    zosSystemName = StringType()
    zosTotalGeneralPurposeProcessors = IntType()
    zosTotalPhysicalMemory = IntType()
    zosTotalZiipProcessors = IntType()
    zosVirtualization = StringType()


class ProcessGroupInstanceProperties(Model):
    agentVersion = StringType()
    appVersion = StringType()
    awsNameTag = StringType()
    azureHostName = StringType()
    azureSiteName = StringType()
    bitness = StringType()
    boshName = StringType()
    conditionalName = StringType()
    customPgMetadata = DictType(StringType)
    customizedName = StringType()
    detectedName = StringType()
    dt_security_context = ListType(StringType())
    ebpfHasPublicTraffic = BooleanType()
    gardenApplicationNames = ListType(StringType())
    gcpZone = StringType()
    hasPublicTraffic = BooleanType()
    installerVersion = StringType()
    isDockerized = BooleanType()
    jvmClrVersion = StringType()
    jvmVendor = StringType()
    listenPorts = ListType(StringType())
    logFileStatus = DictType(StringType)
    logPathLastUpdate = LogPathEntry()
    logSourceState = DictType(StringType)
    metadata = ListType(DictType(StringType))
    modules = ListType(StringType())
    oneAgentCustomHostName = StringType()
    processType = StringType()
    releasesBuildVersion = StringType()
    releasesProduct = StringType()
    releasesStage = StringType()
    releasesVersion = DictType(StringType)
    softwareTechnologies = ListType(ModelType(SoftwareTechnology))
    versionedModules = ListType(DictType(StringType))


class ProcessGroupProperties(Model):
    awsNameTag = StringType()
    azureHostName = StringType()
    azureSiteName = StringType()
    boshName = StringType()
    conditionalName = StringType()
    customPgMetadata = DictType(StringType)
    customizedName = StringType()
    detectedName = StringType()
    dt_security_context = ListType(StringType())
    gcpZone = StringType()
    listenPorts = ListType(StringType())
    metadata = ListType(DictType(StringType))
    oneAgentCustomHostName = StringType()
    softwareTechnologies = ListType(ModelType(SoftwareTechnology))


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


class ServiceProperties(Model):
    agentTechnologyType = StringType()
    akkaActorSystem = StringType()
    applicationBuildVersion = ListType(StringType())
    applicationEnvironment = ListType(StringType())
    applicationName = ListType(StringType())
    applicationReleaseVersion = ListType(StringType())
    awsNameTag = StringType()
    boshName = StringType()
    className = StringType()
    cloudDatabaseProvider = StringType()
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
    serviceType = StringType()
    softwareTechnologies = ListType(ModelType(SoftwareTechnology))
    unifiedServiceIndicators = ListType(StringType())
    webApplicationId = StringType()
    webServerName = StringType()
    webServiceName = StringType()
    webServiceNamespace = StringType()


# Entity classes
class ApplicationEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(ApplicationProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})


class CustomDeviceEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(CustomDeviceProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})


class HostEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(HostProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})


class ProcessGroupInstanceEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(ProcessGroupInstanceProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})


class ProcessGroupEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(ProcessGroupProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})


class QueueEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(QueueProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})


class ServiceEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(ServiceProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})