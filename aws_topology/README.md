# Agent Check: Aws_topology

## Overview

This check monitors [Aws_topology][1] through the StackState Agent.

The Agent Check is still in BETA phase.

## Setup

### Installation

The Aws_topology check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `aws_topology.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your aws_topology performance data.
   See the [sample aws_topology.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

Aws_topology does not include any metrics.

### Service Checks

Aws_topology does not include any service checks.

### Events

The topology scan also emits the following events types:

ec2_state: reports the current state of each EC2 instance found (also classic Elastic LoadBalancer instances)
target_instance_health: for instances of Elastic LoadBalancers V2
aws_agent_check_error: when an error is encountered.

### Topology

Topology from the following AWS resources and their relations is collected by this agent:

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
EC2 Instance (only when not in terminated state)
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

[1]: https://docs.stackstate.com/stackpacks/integrations/aws/aws
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/aws_topology/stackstate_checks/aws_topology/data/conf.yaml.example
