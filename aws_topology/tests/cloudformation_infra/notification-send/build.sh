VERSION=0.0.7
PACKAGE_NAME=notification-send
ACCOUNT_ID=120431062118

cd src && zip -r ../$PACKAGE_NAME-$VERSION.zip .
aws s3 cp ../$PACKAGE_NAME-$VERSION.zip s3://stackstate-helloworld-serverless-$ACCOUNT_ID/
