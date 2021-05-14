from .utils import make_valid_data, create_arn as arn, client_array_operation
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType


class S3OriginConfig(Model):
    OriginAccessIdentity = StringType(required=True)  # TODO

class Origin(Model):
    DomainName = StringType(required=True)
    S3OriginConfig = ModelType(S3OriginConfig)

class OriginList(Model):
    Items = ListType(Origin)

class StringList(Model):
    Enabled = BooleanType()
    Items = ListType(StringType())

class LambdaFunctionAssociation(Model):
    LambdaFunctionARN = StringType(required=True)
    EventType = StringType()

class LambdaFunctionAssociationList(Model):
    Items = ListType(LambdaFunctionAssociation, default=[])

class FunctionAssociation(Model):
    FunctionARN = StringType(required=True)
    EventType = StringType()

class FunctionAssociationList(Model):
    Items = ListType(FunctionAssociation, default=[])

class CacheBehavior(Model):
    TargetOriginId = StringType(required=True)
    PathPattern = StringType(default='*')
    TrustedSigners = ModelType(StringList)  # TODO
    TrustedKeyGroups = ModelType(StringList)  # TODO
    LambdaFunctionAssociations = ModelType(LambdaFunctionAssociationList)
    FunctionAssociations = ModelType(FunctionAssociationList)
    FieldLevelEncryptionId = StringType()  # TODO
    RealtimeLogConfigArn = StringType()  # TODO
    CachePolicyId = StringType()  # TODO
    OriginRequestPolicyId = StringType()  # TODO

class CacheBehaviorList(Model):
    Items = ListType(ModelType(CacheBehavior))

class ViewerCertificate(Model):
    CertificateSource = StringType(required=True)
    IAMCertificateId = StringType()
    ACMCertificateArn = StringType()
    Certificate = StringType()

class Distribution(Model):
    ARN = StringType(required=True)
    Id = StringType(required=True)
    Status = StringType(default="UNKNOWN")
    DomainName = StringType(default="UNKNOWN")
    Aliases = ModelType(StringList)
    Origins = ModelType(OriginList, default={})
    DefaultCacheBehavior = ModelType(CacheBehavior, default={})
    CacheBehaviors = ModelType(CacheBehaviorList, default=[])
    ViewerCertificate = ModelType(ViewerCertificate)  # when we do ACM
    WebACLId = StringType()  # when we do WAF firewall


class CloudfrontCollector(RegisteredResourceCollector):
    API = "cloudfront"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.cloudfront.distribution"

    def collect_distribution(self, distribution):
        return distribution

    def collect_distributions(self):
        for page in client.get_paginator('list_distributions').paginate():
            for distribution in page.get("DistributionList", {}).get('Items', []):
                yield distribution      

    def collect_function(self):
        for page in client.get_paginator('list_function').paginate():
            for function in page.get("FunctionList", {}).get('Items', []):
                yield function      

    def collect_OAIs(self):
        # list_cloud_front_origin_access_identities
        pass

    def process_all(self, filter=None):
        if not filter or 'distributions' in filter:
            self.process_distributions()
        if not filter or 'functions' in filter:
            self.process_functions()

    def process_distributions(self):
        for distribution in self.collect_distributions():
            self.process_distribution(distribution)

    def process_distribution(self, data):
        distribution = Distribution(data, strict=False)
        distribution.validate()
        output = make_valid_data(data)
        if output.CacheBehaviors:
            output.pop('CacheBehaviors')
        for origin in distribution.Origins.Items:
            domain = origin.DomainName
            # bucket-name.s3.region.amazonaws.com
            # bucket-name.s3.amazonaws.com
            # http://bucket-name.s3-website-region.amazonaws.com
            # examplemediastore.data.mediastore.us-west-1.amazonaws.com
            # examplemediapackage.mediapackage.us-west-1.amazonaws.com
            # ec2-203-0-113-25.compute-1.amazonaws.com
            # example-load-balancer-1234567890.us-west-2.elb.amazonaws.com
            # https://example.com
        self.process_cache_behavior(distribution.ARN, distribution.DefaultCacheBehavior)
        for behavior in distribution.CacheBehaviors.Items:
            self.emit_component(
                distribution.ARN + '/' + behavior.PathPattern,
                'aws.cloudfront.cache_behavior',
                {
                    'Name': behavior.PathPattern
                }
            )
            self.process_cache_behavior(distribution.ARN + '/' + behavior.PathPattern, distribution.DefaultCacheBehavior)

    def process_cache_behavior(self, arn, behavior)
        for function in behavior.LambdaFunctionAssociations.Items:
            self.agent.relation(arn, function.LambdaFunctionARN, 'uses service', { "EventType": function.EventType })
        for function in behavior.FunctionAssociation.Items:
            self.agent.relation(arn, function.FunctionARN, 'uses service', { "EventType": function.EventType })

    def process_functions(self):
        for function in self.collect_function():
            self.process_function(function)

    def process_function(self, data):
        pass





