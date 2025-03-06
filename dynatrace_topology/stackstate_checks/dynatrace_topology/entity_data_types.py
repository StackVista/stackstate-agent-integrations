from typing import Optional, List, Dict, Any
from pydantic import Field  # Assuming ForgivingBaseModel supports Pydantic's Field
from stackstate_checks.base.utils.validations_utils import ForgivingBaseModel, AnyUrlStr

# Define your constants if they are not already defined elsewhere
VERIFY_HTTPS = True
TIMEOUT = 30
DOMAIN = "default_domain"
ENVIRONMENT = "production"
RELATIVE_TIME = "now"
API_V2_DEFAULT_FIELDS_STRING = "default_fields"
API_V2_DEFAULT_RELATIVE_TIME = "now"

# Extra classes for reused structures
class SoftwareTechnology(ForgivingBaseModel):
    type: Optional[str] = None
    version: Optional[str] = None


class Relationship(ForgivingBaseModel):
    id: Optional[str] = None
    type: Optional[str] = None


class LogPathEntry(ForgivingBaseModel):
    key: Optional[str] = None
    value: Optional[int] = None


class LogFileStatusEntry(ForgivingBaseModel):
    key: str
    value: str


class LogFileStatus(ForgivingBaseModel):
    logFileStatus: List[LogFileStatusEntry] = Field(default_factory=list)


class StorageStatus(ForgivingBaseModel):
    storageStatus: str


class LogSourceStateEntry(ForgivingBaseModel):
    key: str
    value: StorageStatus


class LogSourceState(ForgivingBaseModel):
    logSourceState: List[LogSourceStateEntry] = Field(default_factory=list)


class ApplicationProperties(ForgivingBaseModel):
    applicationInjectionType: Optional[str] = None
    applicationMatchTarget: Optional[str] = None
    applicationType: Optional[str] = None
    awsNameTag: Optional[str] = None
    boshName: Optional[str] = None
    conditionalName: Optional[str] = None
    customizedName: Optional[str] = None
    detectedName: Optional[str] = None
    dt_security_context: List[str] = Field(default_factory=list)
    gcpZone: Optional[str] = None
    oneAgentCustomHostName: Optional[str] = None
    ruleAppliedMatchType: Optional[str] = None
    ruleAppliedPattern: Optional[str] = None


class CustomDeviceProperties(ForgivingBaseModel):
    dnsNames: List[str] = Field(default_factory=list)
    ipAddress: List[str] = Field(default_factory=list)


class HostProperties(ForgivingBaseModel):
    additionalSystemInfo: List[Dict[str, Any]] = Field(default_factory=list)
    autoInjection: Optional[str] = None
    awsNameTag: Optional[str] = None
    azureComputeModeName: Optional[str] = None
    azureEnvironment: Optional[str] = None
    azureHostNames: List[str] = Field(default_factory=list)
    azureResourceGroupName: Optional[str] = None
    azureSiteNames: List[str] = Field(default_factory=list)
    azureSku: Optional[str] = None
    azureVmScaleSetName: Optional[str] = None
    azureVmSizeLabel: Optional[str] = None
    azureZone: Optional[str] = None
    bitness: Optional[str] = None
    boshAvailabilityZone: Optional[str] = None
    boshDeploymentId: Optional[str] = None
    boshInstanceId: Optional[str] = None
    boshInstanceName: Optional[str] = None
    boshName: Optional[str] = None
    boshStemcellVersion: Optional[str] = None
    cloudPlatformVendorVersion: Optional[str] = None
    cloudType: Optional[str] = None
    conditionalName: Optional[str] = None
    cpuCores: Optional[int] = None
    customHostMetadata: Dict[str, Any] = Field(default_factory=dict)
    customizedName: Optional[str] = None
    detectedName: Optional[str] = None
    dnsNames: List[str] = Field(default_factory=list)
    dt_security_context: List[str] = Field(default_factory=list)
    ebpfDiscoveryMonitored: Optional[bool] = False
    ebpfHasPublicTraffic: Optional[bool] = False
    gceHostName: Optional[str] = None
    gceInstanceId: Optional[str] = None
    gceInstanceName: Optional[str] = None
    gceMachineType: Optional[str] = None
    gceNumericProjectId: Optional[str] = None
    gceProjectId: Optional[str] = None
    gcePublicIpAddresses: List[str] = Field(default_factory=list)
    gcpZone: Optional[str] = None
    hasPublicTraffic: Optional[bool] = False
    hostGroupName: Optional[str] = None
    hypervisorType: Optional[str] = None
    installerPotentialProblem: Optional[bool] = False
    installerSupportAlert: Optional[bool] = False
    installerTrackedDownload: Optional[bool] = False
    installerVersion: Optional[str] = None
    ipAddress: List[str] = Field(default_factory=list)
    isMonitoringCandidate: Optional[bool] = False
    kubernetesLabels: Dict[str, Any] = Field(default_factory=dict)
    logFileStatus: Optional[LogFileStatus] = None
    logPathLastUpdate: Optional[LogPathEntry] = None
    logSourceState: Optional[LogSourceState] = None
    logicalCpuCores: Optional[int] = None
    logicalCpus: Optional[int] = None
    macAddresses: List[str] = Field(default_factory=list)
    memoryTotal: Optional[int] = None
    monitoringMode: Optional[str] = None
    networkZone: Optional[str] = None
    oneAgentCustomHostName: Optional[str] = None
    osArchitecture: Optional[str] = None
    osServices: List[str] = Field(default_factory=list)
    osType: Optional[str] = None
    osVersion: Optional[str] = None
    paasMemoryLimit: Optional[int] = None
    paasVendorType: Optional[str] = None
    physicalMemory: Optional[int] = None
    simultaneousMultithreading: Optional[int] = None
    softwareTechnologies: List[SoftwareTechnology] = Field(default_factory=list)
    standalone: Optional[bool] = False
    standaloneSpecialAgentsOnly: Optional[bool] = False
    state: Optional[str] = None
    virtualCpus: Optional[int] = None
    zosCPUModelNumber: Optional[str] = None
    zosCPUSerialNumber: Optional[str] = None
    zosLparName: Optional[str] = None
    zosSystemName: Optional[str] = None
    zosTotalGeneralPurposeProcessors: Optional[int] = None
    zosTotalPhysicalMemory: Optional[int] = None
    zosTotalZiipProcessors: Optional[int] = None
    zosVirtualization: Optional[str] = None


class ProcessGroupInstanceProperties(ForgivingBaseModel):
    agentVersion: Optional[str] = None
    appVersion: Optional[str] = None
    awsNameTag: Optional[str] = None
    azureHostName: Optional[str] = None
    azureSiteName: Optional[str] = None
    bitness: Optional[str] = None
    boshName: Optional[str] = None
    conditionalName: Optional[str] = None
    customPgMetadata: Dict[str, Any] = Field(default_factory=dict)
    customizedName: Optional[str] = None
    detectedName: Optional[str] = None
    dt_security_context: List[str] = Field(default_factory=list)
    ebpfHasPublicTraffic: Optional[bool] = False
    gardenApplicationNames: List[str] = Field(default_factory=list)
    gcpZone: Optional[str] = None
    hasPublicTraffic: Optional[bool] = False
    installerVersion: Optional[str] = None
    isDockerized: Optional[bool] = False
    jvmClrVersion: Optional[str] = None
    jvmVendor: Optional[str] = None
    listenPorts: List[str] = Field(default_factory=list)
    logFileStatus: Optional[LogFileStatus] = None
    logPathLastUpdate: Optional[LogPathEntry] = None
    logSourceState: Optional[LogSourceState] = None
    metadata: List[Dict[str, Any]] = Field(default_factory=list)
    modules: List[str] = Field(default_factory=list)
    oneAgentCustomHostName: Optional[str] = None
    processType: Optional[str] = None
    releasesBuildVersion: Optional[str] = None
    releasesProduct: Optional[str] = None
    releasesStage: Optional[str] = None
    releasesVersion: Dict[str, Any] = Field(default_factory=dict)
    softwareTechnologies: List[SoftwareTechnology] = Field(default_factory=list)
    versionedModules: List[Dict[str, Any]] = Field(default_factory=list)


class ProcessGroupProperties(ForgivingBaseModel):
    awsNameTag: Optional[str] = None
    azureHostName: Optional[str] = None
    azureSiteName: Optional[str] = None
    boshName: Optional[str] = None
    conditionalName: Optional[str] = None
    customPgMetadata: Dict[str, Any] = Field(default_factory=dict)
    customizedName: Optional[str] = None
    detectedName: Optional[str] = None
    dt_security_context: List[str] = Field(default_factory=list)
    gcpZone: Optional[str] = None
    listenPorts: List[str] = Field(default_factory=list)
    metadata: List[Dict[str, Any]] = Field(default_factory=list)
    oneAgentCustomHostName: Optional[str] = None
    softwareTechnologies: List[SoftwareTechnology] = Field(default_factory=list)


class QueueProperties(ForgivingBaseModel):
    awsNameTag: Optional[str] = None
    boshName: Optional[str] = None
    conditionalName: Optional[str] = None
    customizedName: Optional[str] = None
    detectedName: Optional[str] = None
    dt_security_context: List[str] = Field(default_factory=list)
    gcpZone: Optional[str] = None
    oneAgentCustomHostName: Optional[str] = None
    queueDestinationType: Optional[str] = None
    queueName: Optional[str] = None
    queueVendorName: Optional[str] = None
    softwareTechnologies: List[SoftwareTechnology] = Field(default_factory=list)


class ServiceProperties(ForgivingBaseModel):
    agentTechnologyType: Optional[str] = None
    akkaActorSystem: Optional[str] = None
    applicationBuildVersion: List[str] = Field(default_factory=list)
    applicationEnvironment: List[str] = Field(default_factory=list)
    applicationName: List[str] = Field(default_factory=list)
    applicationReleaseVersion: List[str] = Field(default_factory=list)
    awsNameTag: Optional[str] = None
    boshName: Optional[str] = None
    className: Optional[str] = None
    cloudDatabaseProvider: Optional[str] = None
    conditionalName: Optional[str] = None
    contextRoot: Optional[str] = None
    customizedName: Optional[str] = None
    databaseHostNames: List[str] = Field(default_factory=list)
    databaseName: Optional[str] = None
    databaseVendor: Optional[str] = None
    detectedName: Optional[str] = None
    dt_security_context: List[str] = Field(default_factory=list)
    esbApplicationName: Optional[str] = None
    gcpZone: Optional[str] = None
    ibmCtgGatewayUrl: Optional[str] = None
    ibmCtgServerName: Optional[str] = None
    ipAddress: List[str] = Field(default_factory=list)
    isExternalService: Optional[bool] = False
    oneAgentCustomHostName: Optional[str] = None
    path: Optional[str] = None
    port: Optional[int] = None
    publicCloudId: Optional[str] = None
    publicCloudRegion: Optional[str] = None
    publicDomainName: Optional[str] = None
    remoteEndpoint: Optional[str] = None
    remoteServiceName: Optional[str] = None
    serviceDetectionAttributes: Dict[str, Any] = Field(default_factory=dict)
    serviceTechnologyTypes: List[str] = Field(default_factory=list)
    serviceType: Optional[str] = None
    softwareTechnologies: List[SoftwareTechnology] = Field(default_factory=list)
    unifiedServiceIndicators: List[str] = Field(default_factory=list)
    webApplicationId: Optional[str] = None
    webServerName: Optional[str] = None
    webServiceName: Optional[str] = None
    webServiceNamespace: Optional[str] = None


# Entity classes
class ApplicationEntity(ForgivingBaseModel):
    entityId: str
    type: str
    displayName: str
    properties: Optional[ApplicationProperties] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    managementZones: List[Dict[str, Any]] = Field(default_factory=list)
    fromRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)
    toRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)


class CustomDeviceEntity(ForgivingBaseModel):
    entityId: str
    type: str
    displayName: str
    properties: Optional[CustomDeviceProperties] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    managementZones: List[Dict[str, Any]] = Field(default_factory=list)
    fromRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)
    toRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)


class HostEntity(ForgivingBaseModel):
    entityId: str
    type: str
    displayName: str
    properties: Optional[HostProperties] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    managementZones: List[Dict[str, Any]] = Field(default_factory=list)
    fromRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)
    toRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)


class ProcessGroupInstanceEntity(ForgivingBaseModel):
    entityId: str
    type: str
    displayName: str
    properties: Optional[ProcessGroupInstanceProperties] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    managementZones: List[Dict[str, Any]] = Field(default_factory=list)
    fromRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)
    toRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)


class ProcessGroupEntity(ForgivingBaseModel):
    entityId: str
    type: str
    displayName: str
    properties: Optional[ProcessGroupProperties] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    managementZones: List[Dict[str, Any]] = Field(default_factory=list)
    fromRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)
    toRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)


class QueueEntity(ForgivingBaseModel):
    entityId: str
    type: str
    displayName: str
    properties: Optional[QueueProperties] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    managementZones: List[Dict[str, Any]] = Field(default_factory=list)
    fromRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)
    toRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)


class ServiceEntity(ForgivingBaseModel):
    entityId: str
    type: str
    displayName: str
    properties: Optional[ServiceProperties] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    managementZones: List[Dict[str, Any]] = Field(default_factory=list)
    fromRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)
    toRelationships: Dict[str, List[Relationship]] = Field(default_factory=dict)