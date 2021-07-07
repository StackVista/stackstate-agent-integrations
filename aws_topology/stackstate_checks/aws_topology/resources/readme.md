

Topology

The AWS integration retrieves components and relations for the AWS cloud environment.

Components

The following AWS topology data is available in StackState as components:

S3 Bucket
SQS Queue
SNS Topic
Security Group
Route53 Domain
Route53 Hosted Zone
Redshift Cluster
RDS Instance
Lambda
Lambda Alias
Kinesis Stream
Firehose Delivery Stream
Load Balancer V2
Target Group
Target Group Instance
Load Balancer Classic
EC2 Instance
ECS Cluster
ECS Task
ECS Service
VPN Gateway
VPC
Subnet
DynamoDB Table
DynamoDB Stream
CloudFormation Stack
AutoScaling Group
API Gateway Stage
API Gateway Resource
API Getaway Method

The following relations between components are retrieved:

S3 Bucket → Lambda (notification configuration of the bucket)
SNS Topic → Subscription
Security Group → VPC
Redshift Cluster → VPC
RDS Cluster → RDS Instance
RDS Instance → VPC
RDS Instance → Security Group
Lambda → Event Source Mapping
Lambda → VPC
Lambda → Security Group
Lambda Alias → VPC
Firehose Delivery Stream → Kinesis Source
Firehise Delivery Stream → S3 Bucket Destination(s)
Load Balancer V2 → Security Group
Load Balancer V2 → VPC
Load Balancer V2 → Target Group
Target Group → VPC
Target Group → EC2 Instance
Load Balancer Classic → VPC
Load Balancer Classic → EC2 Instance
Load Balancer Classic → VPC
ECS Task → ECS Cluster
ESC Cluster → ECS Task (when no group service)
ECS Service → ECS Cluster
ECS Cluster → EC2 Instance
ECS Service → Target Group
ECS Service → ECS Task
ECS Service → Route53 Hosted Zone
EC2 Instance → Subnet
EC2 Instance → VPC
EC2 Instance → Security Group
VPN Gateway → VPC
Subnet → VPC
DynamoDB Table → DynamoDB Stream
CloudFormation Stack → CloudFormation Stack Parent
CloudFormation Stack → Any Resource (many supported)
AutoScaling Group → EC2 Instance
AutoScaling Group → Load Balancer Classic
Target Group → AutoScaling Group 
API Gateway Stage → API Gateway Resource
API Gateway Resource → API Gateways Method
API Gateway Method → (Service) Integration Resource (varies)




















Handling a resource

- should work with only one boto call returning info, rest of the calls should be unnesesary for OK check result

TODO check if all components have location_info embedded (and correct_tags)

# all resources

# apigateway



# s3

client.list_buckets().get("Buckets")
    component 
        id = !construct bucket.arn from name
        type = aws.s3
        data =
            ! make_valid_data
            + BucketLocation = client.get_bucket_location(Bucket=bucket_name)[""]
            + Tags = client.get_bucket_tagging(Bucket=bucket_name)["TagSet"] or []
            + location_info
            ! correct_tags

    memory: name -> arn

    client.get_bucket_notification_configuration(Bucket=bucket_name).get("LambdaFunctionConfigurations")
        relation bucket.arn -> lambda.arn, 'uses service' { event_type }

# autoscaling

describe_auto_scaling_groups_page.get('AutoScalingGroups')
    component
        id = data['AutoScalingGroupARN']
        type = aws.autoscaling.group
        data =
            ! make_valid_data
            + location_info
            ! correct_tags

        instance
            relation
                parent arn -> instance_id, use servince, {}
        loadbalancers
            relation
                classic_elb_${lb.name} -> parent arn

            instance
                delete relation 'classic_elb_' + load_balancer_name + '-uses service-' + instance_id ??? is this a fix?
        targetgroup
            relation
                arn -> parent arn


    memory name -> arn

    auto_scaling = {}
    for describe_auto_scaling_groups_page in :
        for auto_scaling_group_description_raw in describe_auto_scaling_groups_page.get('AutoScalingGroups') or []:
            auto_scaling_group_description = make_valid_data(auto_scaling_group_description_raw)
            auto_scaling_group_arn = auto_scaling_group_description['AutoScalingGroupARN']
            auto_scaling_group_description.update(location_info)
            auto_scaling_group_name = auto_scaling_group_description['AutoScalingGroupName']
            agent.component(auto_scaling_group_arn, 'aws.autoscaling.group',
                            correct_tags(auto_scaling_group_description))
            auto_scaling[auto_scaling_group_name] = auto_scaling_group_arn
            for instance in auto_scaling_group_description['Instances']:
                instance_id = instance['InstanceId']
                agent.relation(auto_scaling_group_arn, instance_id, 'uses service', {})

            for load_balancer_name in auto_scaling_group_description['LoadBalancerNames']:
                agent.relation('classic_elb_' + load_balancer_name, auto_scaling_group_arn, 'uses service', {})

                for instance in auto_scaling_group_description['Instances']:
                    # removing elb instances if there are any
                    instance_id = instance['InstanceId']
                    relation_id = 'classic_elb_' + load_balancer_name + '-uses service-' + instance_id
                    agent.delete(relation_id)

            for target_group_arn in auto_scaling_group_description['TargetGroupARNs']:
                agent.relation(target_group_arn, auto_scaling_group_arn, 'uses service', {})

                for instance in auto_scaling_group_description['Instances']:
                    # removing elb instances if there are any
                    instance_id = instance["InstanceId"]
                    relation_id = target_group_arn + '-uses service-' + instance_id
                    agent.delete(relation_id)
    return auto_scaling




# s3

Bucket

s3.AnalyticsConfigurations.StorageClassAnalysis.DataExport.Destination -> Bucket
s3.BucketEncryption.ServerSideEncryptionConfiguration.ServerSideEncryptionByDefault => KMSMasterKey
s3.InventoryConfiguration.Destination -> Bucket
s3.LifecycleConfiguration.Rules(Id)
s3.LoggingConfiguration -> Bucket
s3.NotificationConfiguration
  -> lambda
  -> sns topic
  -> sqs queue
s3.ReplicationConfiguration.ReplicationRule -> Bucket

AccessPoint
    Bucket
    Vpc
    Policy

BucketPolicy
    Bucket

StorageLensConfiguartion
    Include -> [Bucket]
    Exclude -> [Bucket]
    DataExport -> Bucket

ObjectLambdaAccessPoint
    AccessPoint
    Transformation: [Lambda]

ObjectLambdaAccessPointPolicy:
    ObjectLambdaAccessPoint

s3 on outposts:


