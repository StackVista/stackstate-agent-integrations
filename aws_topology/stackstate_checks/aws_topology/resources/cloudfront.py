from .utils import make_valid_data, create_arn as arn, client_array_operation
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ModelType, ListType, BooleanType
import json


"""
structural todo's
origin should be component otherwise all origins are same as distribution -> too many relations

component todo's
TODO list_realtime_log_configs
TODO list_streaming_distributions 

relation todo's
TODO origin-access-identity connection can be with S3 get_bucket_acl TODO
TODO Distribution.WebACLId when we do WAF firewall
TODO realtime logs link to kinesis
TODO streaming distribution <-> s3 + oai
"""


class S3OriginConfig(Model):
    OriginAccessIdentity = StringType(required=True)


class Origin(Model):
    DomainName = StringType(required=True)
    S3OriginConfig = ModelType(S3OriginConfig)


class OriginList(Model):
    Items = ListType(ModelType(Origin))


class StringList(Model):
    Enabled = BooleanType()
    Items = ListType(StringType())


class LambdaFunctionAssociation(Model):
    LambdaFunctionARN = StringType(required=True)
    EventType = StringType()


class LambdaFunctionAssociationList(Model):
    Items = ListType(ModelType(LambdaFunctionAssociation), default=[])


class FunctionAssociation(Model):
    FunctionARN = StringType(required=True)
    EventType = StringType()


class FunctionAssociationList(Model):
    Items = ListType(ModelType(FunctionAssociation), default=[])


class CacheBehavior(Model):
    TargetOriginId = StringType(required=True)
    PathPattern = StringType(default='*')
    TrustedKeyGroups = ModelType(StringList)
    LambdaFunctionAssociations = ModelType(LambdaFunctionAssociationList)
    FunctionAssociations = ModelType(FunctionAssociationList)
    FieldLevelEncryptionId = StringType()
    RealtimeLogConfigArn = StringType()  # TODO
    CachePolicyId = StringType()
    OriginRequestPolicyId = StringType()


class CacheBehaviorList(Model):
    Items = ListType(ModelType(CacheBehavior), default=[])


class ViewerCertificate(Model):
    CertificateSource = StringType(required=True)
    IAMCertificateId = StringType()
    ACMCertificateArn = StringType()


class Distribution(Model):
    ARN = StringType(required=True)
    Id = StringType(required=True)
    Status = StringType(default="UNKNOWN")
    DomainName = StringType(default="UNKNOWN")
    Aliases = ModelType(StringList)
    Origins = ModelType(OriginList)  # default={}
    DefaultCacheBehavior = ModelType(CacheBehavior)  # , default={}
    CacheBehaviors = ModelType(CacheBehaviorList, default={})  # , default=[]
    ViewerCertificate = ModelType(ViewerCertificate)
    WebACLId = StringType()


class FunctionMetadata(Model):
    FunctionARN = StringType(required=True)


class Function(Model):
    Name = StringType(default="UNKNOWN")
    Status = StringType(default="UNKNOWN")
    FunctionMetadata = ModelType(FunctionMetadata, required=True)


class OAI(Model):
    Id = StringType(required=True)


class KeyGroupConfig(Model):
    Name = StringType(default="UNKNOWN")
    Items = ListType(StringType)


class KeyGroup(Model):
    Id = StringType(required=True)
    KeyGroupConfig = ModelType(KeyGroupConfig, required=True)


class PublicKey(Model):
    Id = StringType(required=True)
    Name = StringType(default="UNKNOWN")


class EncryptionEntity(Model):
    PublicKeyId = StringType(required=True)
    ProviderId = StringType(default="UNKNOWN")


class EncryptionEntityList(Model):
    Items = ListType(ModelType(EncryptionEntity), default=[])


class FieldEncryptionProfile(Model):
    Id = StringType(required=True)
    Name = StringType(default="UNKNOWN")
    EncryptionEntities = ModelType(EncryptionEntityList)


class ContentTypeProfile(Model):
    ProfileId = StringType(required=True)


class ContentTypeProfileList(Model):
    Items = ListType(ModelType(ContentTypeProfile))


class ContentTypeProfileConfig(Model):
    ContentTypeProfiles = ModelType(ContentTypeProfileList)


class FieldEncryptionConfiguration(Model):
    Id = StringType(required=True)
    ContentTypeProfileConfig = ModelType(ContentTypeProfileConfig) 


class CachePolicyConfig(Model):
    Name = StringType(default="UNKNOWN")


class CachePolicy(Model):
    Id = StringType(required=True)
    CachePolicyConfig = ModelType(CachePolicyConfig)


class CachePolicyWrapper(Model):
    Type = StringType(required=True)
    CachePolicy = ModelType(CachePolicy)


class OriginRequestPolicyConfig(Model):
    Name = StringType(default="UNKNOWN")


class OriginPolicy(Model):
    Id = StringType(required=True)
    OriginRequestPolicyConfig = ModelType(OriginRequestPolicyConfig)


class OriginPolicyWrapper(Model):
    Type = StringType(required=True)
    OriginRequestPolicy = ModelType(OriginPolicy)


class CloudfrontCollector(RegisteredResourceCollector):
    API = "cloudfront"
    API_TYPE = "global"
    COMPONENT_TYPE = "aws.cloudfront.distribution"

    def collect_distribution(self, distribution):
        return distribution

    def collect_distributions(self):
        for page in self.client.get_paginator('list_distributions').paginate():
            for distribution in page.get("DistributionList", {}).get('Items', []):
                yield distribution      

    def collect_function(self):
        # TODO paginating this one gives an error but it does have NextMarker!
        for function in self.client.list_functions().get('FunctionList', {}).get('Items', []):
            yield function

    def collect_oais(self):
        for page in self.client.get_paginator('list_cloud_front_origin_access_identities').paginate():
            for oai in page.get("CloudFrontOriginAccessIdentityList", {}).get('Items', []):
                yield oai              

    def collect_key_groups(self):
        for group in self.client.list_key_groups().get("KeyGroupList", {}).get('Items', []):
            yield group.get('KeyGroup')

    def collect_public_keys(self):
        for key in self.client.list_public_keys().get("PublicKeyList", {}).get('Items', []):
            yield key              

    def collect_field_encryption_profiles(self):
        for profile in self.client.list_field_level_encryption_profiles().get("FieldLevelEncryptionProfileList", {}).get('Items', []):
            yield profile
        
    def collect_field_encryption_configurations(self):
        for configuration in self.client.list_field_level_encryption_configs().get("FieldLevelEncryptionList", {}).get('Items', []):
            yield configuration 

    def collect_cache_policies(self):
        for policy in self.client.list_cache_policies().get("CachePolicyList", {}).get('Items', []):
            yield policy
        
    def collect_origin_policies(self):
        for policy in self.client.list_origin_request_policies().get("OriginRequestPolicyList", {}).get('Items', []):
            yield policy

    def process_all(self, filter=None):
        if not filter or 'distributions' in filter:
            self.process_distributions()
        if not filter or 'functions' in filter:
            self.process_functions()
        if not filter or 'oais' in filter:
            self.process_oais()
        if not filter or 'publickeys' in filter:
            self.process_public_keys()
        if not filter or 'fieldencryption_configs' in filter:
            self.process_field_encryptions()
        if not filter or 'policies' in filter:
            self.process_policies()

    def process_policies(self):
        for policy in self.collect_cache_policies():
            self.process_cache_policy(policy)
        for policy in self.collect_origin_policies():
            self.process_origin_policy(policy)

    def process_cache_policy(self, data):
        output = make_valid_data(data)
        policy = CachePolicyWrapper(data, strict=False)
        policy.validate()
        output["Name"] = policy.CachePolicy.CachePolicyConfig.Name
        self.emit_component(policy.CachePolicy.Id, 'aws.cloudfront.cachepolicy', output)

    def process_origin_policy(self, data):
        output = make_valid_data(data)
        policy = OriginPolicyWrapper(data, strict=False)
        policy.validate()
        output["Name"] = policy.OriginRequestPolicy.OriginRequestPolicyConfig.Name
        self.emit_component(policy.OriginRequestPolicy.Id, 'aws.cloudfront.originpolicy', output)

    def process_field_encryptions(self):
        for profile in self.collect_field_encryption_profiles():
            self.process_field_encryption_profile(profile)
        for config in self.collect_field_encryption_configurations():
            self.process_field_encryption_configuration(config)

    def process_field_encryption_configuration(self, data):
        output = make_valid_data(data)
        config = FieldEncryptionConfiguration(data, strict=False)
        config.validate()
        self.emit_component(config.Id, 'aws.cloudfront.fieldencryption_config', output)
        for item in config.ContentTypeProfileConfig.ContentTypeProfiles.Items:
            self.agent.relation(config.Id, item.ProfileId, 'uses service', {})

    def process_field_encryption_profile(self, data):
        output = make_valid_data(data)
        profile = FieldEncryptionProfile(data, strict=False)
        profile.validate()
        output["Name"] = profile.Name
        self.emit_component(profile.Id, 'aws.cloudfront.fieldencryption_profile', output)
        for item in profile.EncryptionEntities.Items:
            self.agent.relation(profile.Id, item.PublicKeyId, 'uses service', {})

    def process_public_keys(self):
        for key in self.collect_public_keys():
            self.process_public_key(key)
        for group in self.collect_key_groups():
            self.process_key_group(group)

    def process_key_group(self, data):
        output = make_valid_data(data)
        group = KeyGroup(data, strict=False)
        group.validate()
        output["Name"] = group.KeyGroupConfig.Name
        self.emit_component(group.Id, 'aws.cloudfront.keygroup', output)
        for key in group.KeyGroupConfig.Items:
            self.agent.relation(group.Id, key, 'uses service', {})

    def process_public_key(self, data):
        output = make_valid_data(data)
        key = PublicKey(data, strict=False)
        key.validate()
        output["Name"] = key.Name
        self.emit_component(key.Id, 'aws.cloudfront.publickey', output)

    def process_oais(self):
        for oai in self.collect_oais():
            self.process_oai(oai)

    def process_distributions(self):
        for distribution in self.collect_distributions():
            self.process_distribution(distribution)

    def process_distribution(self, data):
        distribution = Distribution(data, strict=False)
        distribution.validate()
        output = make_valid_data(data)
        if output.get('CacheBehaviors'):
            output.pop('CacheBehaviors')
        self.emit_component(distribution.ARN, 'aws.cloudfront.distribution', output)
        for origin in distribution.Origins.Items:
            # should origin become component?
            domain = origin.DomainName
            if origin.S3OriginConfig:
                self.agent.relation(distribution.ARN, origin.S3OriginConfig.OriginAccessIdentity, 'uses service', {})
            # bucket-name.s3.region.amazonaws.com
            # bucket-name.s3.amazonaws.com
            # http://bucket-name.s3-website-region.amazonaws.com
            # examplemediastore.data.mediastore.us-west-1.amazonaws.com
            # examplemediapackage.mediapackage.us-west-1.amazonaws.com
            # ec2-203-0-113-25.compute-1.amazonaws.com
            # example-load-balancer-1234567890.us-west-2.elb.amazonaws.com
            # https://example.com
        self.process_cache_behavior(distribution.ARN + '/behavior:default', distribution.DefaultCacheBehavior)
        for behavior in distribution.CacheBehaviors.Items:
            self.emit_component(
                distribution.ARN + '/behavior:' + behavior.PathPattern,
                'aws.cloudfront.cache_behavior',
                {
                    'Name': behavior.PathPattern
                }
            )
            self.process_cache_behavior(distribution.ARN + '/behavior:' + behavior.PathPattern, distribution.DefaultCacheBehavior)
        if distribution.ViewerCertificate:
            source = distribution.ViewerCertificate.CertificateSource
            if source == 'IAMCertificateId':
                self.agent.relation(distribution.ARN, distribution.ViewerCertificate.IAMCertificateId, 'uses service', {})
            elif source == 'ACMCertificateArn':
                self.agent.relation(distribution.ARN, distribution.ViewerCertificate.ACMCertificateArn, 'uses service', {})

    def process_cache_behavior(self, arn, behavior):
        for function in behavior.LambdaFunctionAssociations.Items:
            self.agent.relation(arn, function.LambdaFunctionARN, 'uses service', { "EventType": function.EventType })
        for function in behavior.FunctionAssociations.Items:
            self.agent.relation(arn, function.FunctionARN, 'uses service', { "EventType": function.EventType })
        if behavior.TrustedKeyGroups:
            for keygroup in behavior.TrustedKeyGroups.Items:
                self.agent.relation(arn, keygroup, 'uses service', {})
        if behavior.FieldLevelEncryptionId:
            self.agent.relation(arn, behavior.FieldLevelEncryptionId, 'uses service', {})
        if behavior.CachePolicyId:
            self.agent.relation(arn, behavior.CachePolicyId, 'uses service', {})
        if behavior.OriginRequestPolicyId:
            self.agent.relation(arn, behavior.OriginRequestPolicyId, 'uses service', {})

    def process_functions(self):
        for function in self.collect_function():
            self.process_function(function)

    def process_function(self, data):
        function = Function(data, strict=False)
        function.validate()
        output = make_valid_data(data)
        self.emit_component(
            function.FunctionMetadata.FunctionARN,
            'aws.cloudfront.function',
            output
        )
    
    def process_oai(self, data):
        output = make_valid_data(data)
        oai = OAI(data, strict=False)
        oai.validate()
        self.emit_component('origin-access-identity/cloudfront/' + oai.Id, 'aws.cloudfront.oai', output)
