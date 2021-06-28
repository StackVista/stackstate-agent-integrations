PACKAGE_NAME=xray-trace
STACK_NAME="xray-test"
#TEMPLATE_PATH=../xray_template.yaml

#echo "Creating the stack"
#echo $PWD
#aws cloudformation create-stack \
#--stack-name $STACK_NAME \
#--template-body file://$TEMPLATE_PATH \
#--capabilities CAPABILITY_NAMED_IAM \
#--tags xray-integration=True
#
#aws cloudformation wait stack-create-complete --stack-name $STACK_NAME
echo "Stack Created"

echo "Creating the package and uploading to s3"
pip install aws-xray-sdk==2.4.2 -t src/
zip -r $PACKAGE_NAME.zip src/
echo $PWD
#aws s3 cp ../$PACKAGE_NAME.zip s3://xray-trace-test/
