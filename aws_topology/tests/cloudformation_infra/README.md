# CloudFormation Infra Tests

Use these CloudFormation templates to quickly set up an AWS environment with all agent-supported resources, and complex relations between them. Here's some info on the purpose of each template, along with the order they should be deployed. The names of the templates are as shown in the headers.

## 1. `stackstate-resources-debug`

This template doesn't exist here - it's in stackpacks, and is the debug version of the CloudFormation template deployed to customer environments. This will create the IAM role the agent needs, and the S3 bucket for VPC flowlogs etc.

### Parameters

This template is documented fully in the Stackstate docs, but here's a quick summary of parameters:

- External ID: A shared secret value between the agent and IAM role. Typically for testing purposes, the value `pancakes` has been used.
- Main Region: Set this to the region in which the IAM role is used. This template should be deployed in every region where the agent scans, and every template should have the same value. If the region set does not match the region it is deployed in, it will not attempt to create another IAM role. Set all instances to `eu-west-1`.
- StsAccountId: The account containing your IAM user. The stackstate-infosec account ID is `669835386582`.

## 2. `stackstate-base`

The base template to be deployed in any AWS account where integration tests are taking place. This sets up the base VPC necessary for all other resources to be built on.

### Parameters

- Resources Stack Name: Set this to the name of the stack you created above. By default this is `stackstate-resources-debug`.
- VPC CIDR: A /16 subnet used by the VPC created in this stack. Start at `10.0.0.0/16`, then `10.1.0.0/16`, `10.2.0.0/16` etc. Use a different subnet for every `stackstate-base` template deployed, so there are no IP conflicts or overlaps.

## 3. `stackstate-main-account-secondary-region`

Contains a few resources so that are then linked to in the main-account-main-region template, for testing cross-region relations. Typically this is deployed in region `us-east-1`.

## 4. `stackstate-main-account-main-region`

This contains the majority of the resources. Set this up in the primary account, in the primary region. You'll need to copy the outputs of main-account-secondary-region into the parameters section of this template during the creation process.

### Parameters

- Key Pair Name: The name of an SSH key you uploaded in the EC2 console. If you don't have a key uploaded, leave this blank; it just won't be possible to connect to the created EC2 instance.
- Secondary Region SQS Queue: The output of the previous template, so it can create a cross-region link to the resource.

## 5. `stackstate-helloworld-serverless`

A more realistic test, designed for demo purposes. Contains a working application that transfers data across the VPC, to test VPC flowlogs.

This one is a little more complex to deploy:

1. Comment out all resources in the template except the S3 bucket, and deploy the template
2. Go to https://github.com/jkehler/awslambda-psycopg2 and get the folder `psycopg2-3.8`
3. Rename it to `psycopg2` and place it in `notification-send/src`. This is a PostgreSQL pre-compiled binary that is not included in lambda
4. Check the `ACCOUNT_ID` variable is set correct in `notification-send/build.sh` and then run this script with access to the target AWS account
5. Uncomment the rest of the Cfn template, and deploy it

This is necessary because the lambda function that reads from the RDS database needs a driver that we can't include in the template. TODO: make this easier to automatically deploy

## Deleting templates

As each template depends on each other, delete them in the reverse order.

- `stackstate-base` can only be deleted once there are no resources uses the VPC it creates, so be sure that there are no manually created resources using it. You can debug this by starting with Network Interfaces in the EC2 console to see what resources have IP addresses in the subnets, then finding and deleting the resources that use those interfaces.
- `stackstate-resources-debug` has an S3 bucket - S3 buckets can't be deleted unless they're empty. Before deleting the template, go to S3 and click the "Empty" button on the S3 bucket starting with `stackstate-logs-`.
