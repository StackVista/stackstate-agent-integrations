listen_for = {
    's3.amazonaws.com': {
        'CreateBucket': True,
        'DeleteBucket': True
    },
    'redshift.amazonaws.com': {
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
    'dynamodb.amazonaws.com': {
        'CreateTable': True,
        'DeleteTable': True
        # TagResource
        # UntagResource
        # UpdateTable
        # UpdateTimeToLive
        # UpdateGlobalTable
        # CreateGlobalTable

        # events
        # RestoreTableFromBackup
        # RestoreTableToPointInTime
        # DeleteBackup
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
