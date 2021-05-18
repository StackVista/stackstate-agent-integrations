PACKAGE_NAME=notification-send
ACCOUNT_ID=120431062118

pipenv lock -r | sed 's/-e //g' | pip install --upgrade -r /dev/stdin --target src/
cd src && zip -r ../$PACKAGE_NAME.zip .
aws s3 cp ../$PACKAGE_NAME.zip s3://stackstate-helloworld-serverless-$ACCOUNT_ID/
