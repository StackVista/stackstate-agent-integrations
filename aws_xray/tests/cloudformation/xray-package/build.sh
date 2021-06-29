PACKAGE_NAME=xray-trace
STACK_NAME="xray-test"
TEMPLATE_PATH=../xray_template.yaml
BUCKET_NAME=xray-trace-test

echo "Setting up the AWS configuration"
source ./.setup-scripts/setup_aws.sh
cd aws_xray/tests/cloudformation/xray-package
echo $xray
pip install awscli
pip install aws-xray-sdk==2.4.2 -t src/
apt-get install -y zip
echo "Creating the package..."
zip -r $PACKAGE_NAME.zip src/ > /dev/null
echo $PWD
echo "Uploading the package to s3..."
aws s3 mb s3://$BUCKET_NAME --region $AWS_REGION
aws s3 cp $PACKAGE_NAME.zip s3://$BUCKET_NAME/

echo "Creating the stack"
aws cloudformation create-stack \
--stack-name $STACK_NAME \
--template-body file://$TEMPLATE_PATH \
--capabilities CAPABILITY_NAMED_IAM \
--tags xray-integration=True

aws cloudformation wait stack-create-complete --stack-name $STACK_NAME
echo "Stack Created"