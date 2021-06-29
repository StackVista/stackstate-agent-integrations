PACKAGE_NAME=xray-trace
STACK_NAME="xray-test"
TEMPLATE_PATH=../xray_template.yaml
BUCKET_NAME=xray-trace-test

echo "Setting up the AWS configuration"
source ./.setup-scripts/setup_aws.sh
pip install awscli

cd $xray/src
pip install aws-xray-sdk==2.4.2 -t .
apt-get install -y zip
echo "Creating the package..."
zip -r ../$PACKAGE_NAME.zip . > /dev/null
echo $PWD
echo "Uploading the package to s3..."
aws s3 mb s3://$BUCKET_NAME --region $AWS_REGION
aws s3 cp ../$PACKAGE_NAME.zip s3://$BUCKET_NAME/

echo "Creating the stack"
aws cloudformation create-stack \
--stack-name $STACK_NAME \
--template-body file://$TEMPLATE_PATH \
--capabilities CAPABILITY_NAMED_IAM \
--tags Key=xray-integration-test,Value=True

aws cloudformation wait stack-create-complete --stack-name $STACK_NAME
echo "Stack Created"