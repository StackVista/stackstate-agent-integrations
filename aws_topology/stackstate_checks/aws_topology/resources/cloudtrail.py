listen_for = {
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
