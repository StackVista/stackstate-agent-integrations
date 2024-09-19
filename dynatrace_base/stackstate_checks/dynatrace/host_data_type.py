from schematics import Model
from schematics.types import IntType, StringType, ListType, BooleanType, ModelType, DictType

class AdditionalSystemInfo(Model):
    key = StringType()
    value = StringType()

class SoftwareTechnology(Model):
    type = StringType()

class LogPathLastUpdate(Model):
    value = IntType()
    key = StringType()

class HostProperties(Model):
    additionalSystemInfo = DictType(StringType)
    autoInjection = StringType(choices=["ENABLED", "DISABLED"])   # Sample Enum
    awsNameTag = StringType()
    azureComputeModeName = StringType(choices=["MODE_1", "MODE_2"])  # Sample Enum
    azureEnvironment = StringType()
    azureHostNames = ListType(StringType())
    azureResourceGroupName = StringType()
    azureSiteNames = ListType(StringType())
    azureSku = StringType(choices=["SKU_TYPE_1", "SKU_TYPE_2"])  # Sample Enum
    azureVmScaleSetName = StringType()
    azureVmSizeLabel = StringType()
    azureZone = StringType()
    bitness = StringType(choices=["32", "64"])  # Sample Enum
    boshAvailabilityZone = StringType()
    boshDeploymentId = StringType()
    boshInstanceId = StringType()
    boshInstanceName = StringType()
    boshName = StringType()
    boshStemcellVersion = StringType()
    cloudPlatformVendorVersion = StringType()
    cloudType = StringType(choices=["CLOUD_TYPE_1", "CLOUD_TYPE_2"])   # Sample Enum
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
    hypervisorType = StringType(choices=["HYPERVISOR_TYPE_1", "HYPERVISOR_TYPE_2"])  # Sample Enum
    installerPotentialProblem = BooleanType()
    installerSupportAlert = BooleanType()
    installerTrackedDownload = BooleanType()
    installerVersion = StringType()
    ipAddress = ListType(StringType())
    isMonitoringCandidate = BooleanType()
    kubernetesLabels = DictType(StringType)
    logFileStatus = DictType(StringType)
    logPathLastUpdate = DictType(StringType)
    logSourceState = DictType(StringType)
    logicalCpuCores = IntType()
    logicalCpus = IntType()
    macAddresses = ListType(StringType())
    memoryTotal = IntType()
    monitoringMode = StringType(choices=["MODE_1", "MODE_2"])  # Sample Enum
    networkZone = StringType()
    oneAgentCustomHostName = StringType()
    osArchitecture = StringType(choices=["ARCH_1", "ARCH_2"])  # Sample Enum
    osServices = ListType(StringType())
    osType = StringType(choices=["OS_TYPE_1", "OS_TYPE_2"])  # Sample Enum
    osVersion = StringType()
    paasMemoryLimit = IntType()
    paasVendorType = StringType(choices=["VENDOR_TYPE_1", "VENDOR_TYPE_2"])  # Sample Enum
    physicalMemory = IntType()
    simultaneousMultithreading = IntType()
    softwareTechnologies = ListType(ModelType(SoftwareTechnology))
    standalone = BooleanType()
    standaloneSpecialAgentsOnly = BooleanType()
    state = StringType(choices=["RUNNING", "STOPPED"])  # Sample Enum
    virtualCpus = IntType()
    zosCPUModelNumber = StringType()
    zosCPUSerialNumber = StringType()
    zosLparName = StringType()
    zosSystemName = StringType()
    zosTotalGeneralPurposeProcessors = IntType()
    zosTotalPhysicalMemory = IntType()
    zosTotalZiipProcessors = IntType()
    zosVirtualization = StringType()

class Relationship(Model):
    id = StringType()
    type = StringType()

class HostEntity(Model):
    entityId = StringType(required=True)
    type = StringType(required=True)
    displayName = StringType(required=True)
    properties = ModelType(HostProperties)
    tags = ListType(DictType(StringType), default=[])
    managementZones = ListType(DictType(StringType), default=[])
    fromRelationships = DictType(ListType(ModelType(Relationship)), default={})
    toRelationships = DictType(ListType(ModelType(Relationship)), default={})