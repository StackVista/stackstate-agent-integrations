# CloudFormation Infra Tests

Use these CloudFormation templates to quickly set up an AWS environment with all agent-supported resources, and complex relations between them. Here's some info on the purpose of each template, along with the order they should be deployed:

## 1. stackstate-resources-debug

This template doesn't exist here - it's in stackpacks, and is the debug version of the CloudFormation template deployed to customer environments. This will create the IAM role the agent needs, and the S3 bucket for VPC flowlogs etc.

## 2. base

The base template to be deployed in any AWS account where integration tests are taking place. This sets up the base VPC necessary for all other resources to be built on.

## 3. main-account-secondary-region

Contains a few resources so that are then linked to in the main-account-main-region template, for testing cross-region relations.

## 4. main-account-main-region

This contains the majority of the resources. Set this up in the primary account, in the primary region. You'll need to copy the outputs of main-account-secondary-region into the parameters section of this template during the creation process.

## 5. helloworld-serverless

A more realistic test, designed for demo purposes. Contains a working application that transfers data across the VPC, to test VPC flowlogs.

This one is a little more complex to deploy:

1. Comment out all resources in the template except the S3 bucket, and deploy the template
2. Go to https://github.com/jkehler/awslambda-psycopg2 and get the folder `psycopg2-3.8`
3. Rename it to `psycopg2` and place it in `notification-send/src`. This is a PostgreSQL pre-compiled binary that is not included in lambda
4. Check the `ACCOUNT_ID` variable is set correct in `notification-send/build.sh` and then run this script with access to the target AWS account
5. Uncomment the rest of the Cfn template, and deploy it

This is necessary because the lambda function that reads from the RDS database needs a driver that we can't include in the template. TODO: make this easier to automatically deploy
