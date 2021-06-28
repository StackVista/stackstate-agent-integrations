echo "Deleting the S3 bucket "
echo $BUCKET_NAME
aws s3 rm s3://xray-trace-test/xray-trace.zip
aws s3 rb s3://xray-trace-test --force
aws cloudformation delete-stack --stack-name "xray-test"
aws cloudformation wait stack-delete-complete --stack-name "xray-test"
echo "Done"
