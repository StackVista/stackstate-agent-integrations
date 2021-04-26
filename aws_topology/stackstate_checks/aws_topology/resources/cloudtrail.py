from schematics import Model
from schematics.types import StringType, ModelType


class Sqs_Generic(Model):
    class RequestParameters(Model):
        queueUrl = StringType(required=True)

    requestParameters = ModelType(RequestParameters, required=True)


class Sqs_CreateQueue(Model):
    class RequestParameters(Model):
        queueName = StringType(required=True)

    requestParameters = ModelType(RequestParameters, required=True)


listen_for = {
    's3.amazonaws.com': {
        'CreateBucket': True,
        'DeleteBucket': True
    },
    'redshift.amazonaws.com' : {
        'CreateCluster': True,
        'DeleteCluster': True
    },
    'rds.amazonaws.com': {
        'CreateDBInstance': True,
        'CreateDBCluster': True,
        'DeleteDBInstance': True,
        'DeleteDBCluster': True
    },
    'elasticloadbalancing.amazonaws.com': {
        'CreateLoadBalancer': True,
        'RegisterInstancesWithLoadBalancer': True,
        'CreateTargetGroup': True,
        'CreateListener': True,
        'RegisterTargets': True,
        'DeleteTargetGroup': True,
        'DeleteLoadBalancer': True
    },
    'ec2.amazonaws.com': {
        'RunInstances': True
    },
    'sqs.amazonaws.com': {
        'CreateQueue': Sqs_CreateQueue,
        'DeleteQueue': Sqs_Generic,
        'AddPermission': True,
        'RemovePermission': True,
        'SetQueueAttributes': Sqs_Generic,
        'TagQueue': Sqs_Generic,
        'UntagQueue': Sqs_Generic,
        'PurgeQueue': Sqs_Generic  # should emit event instead
    },
    'sns.amazonaws.com': {
        'CreateTopic': True,
        'DeleteTopic': True
        # CreateTopic
        # DeleteTopic
        # CreatePlatformEndpoint
        # DeleteEndpoint
        # CreatePlatformApplication
        # DeletePlatformApplication
        # SetEndpointAttributes
        # SetPlatformApplicationAttributes
        # SetSMSAttributes
        # SetSubscriptionAttributes
        # SetTopicAttributes        
    },
    'firehose.amazonaws.com': {
        'CreateDeliveryStream': True,
        'DeleteDeliveryStream': True
        # UpdateDestination
        # TagDeliveryStream
        # UntagDeliveryStream
        # StartDeliveryStreamEncryption
        # StopDeliveryStreamEncryption
    },
    'kinesis.amazonaws.com': {
        'CreateStream': True,
        'DeleteStream': True
        # DisableEnhancedMonitoring
        # EnableEnhancedMonitoring
        # IncreaseStreamRetentionPeriod
        # DecreaseStreamRetentionPeriod
        # MergeShards
        # RegisterStreamConsumer
        # DeregisterStreamConsumer
        # AddTagsToStream
        # RemoveTagsFromStream
        # StartStreamEncryption
        # StopStreamEncryption
        # SplitShard
        # UpdateShardCount        
    },
    'dynamodb.amazonaws.com': {
        'CreateTable': True,
        'DeleteTable': True
    },
    'lambda.amazonaws.com': {
        'CreateFunction20150331': True,
        'UpdateFunctionConfiguration20150331v2': True,
        'PublishVersion20150331': True,
        'AddPermission20150331v2': True,
        'TagResource20170331v2': True,
        'CreateEventSourceMapping20150331': True,
        'DeleteFunction20150331': True
        # CreateFunction
        # DeleteFunction
        # AddLayerVersionPermission
        # AddPermission
        # RemovePermission
        # CreateEventSourceMapping
        # DeleteEventSourceMapping
        # UpdateEventSourceMapping
        # UpdateFunctionCode
        # UpdateFunctionConfiguration        
    },
    'ecs.amazonaws.com': {
        'CreateCluster': True,
        'CreateService': True
    }
}