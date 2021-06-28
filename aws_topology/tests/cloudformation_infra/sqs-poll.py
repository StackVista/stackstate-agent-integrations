import sys
import os
import json
from time import sleep
import boto3
import psycopg2

secretsmanager = boto3.client("secretsmanager")
secret = json.loads(secretsmanager.get_secret_value(SecretId=os.environ.get("SECRET")).get("SecretString"))
rds_host = secret.get("host")
rds_username = secret.get("username")
rds_user_pwd = secret.get("password")
try:
    conn = psycopg2.connect(host=rds_host, user=rds_username, password=rds_user_pwd, database="postgres")
except:
    print("ERROR: Could not connect to Postgres instance.")
    sys.exit(1)
print("SUCCESS: Connection to RDS Postgres instance succeeded")
sqs = boto3.client("sqs")
queue = os.environ.get("SQS_QUEUE")
while True:
    messages = sqs.receive_message(QueueUrl=queue).get("Messages")
    if messages is not None:
        with conn.cursor() as cur:
            for message in messages:
                body = json.loads(message.get("Body")).get("Input")
                cur.execute(
                    "insert into mailing_list (name, email) values(%s, %s)",
                    (body.get("name"), body.get("email")),
                )
                sqs.delete_message(QueueUrl=queue, ReceiptHandle=message.get("ReceiptHandle"))
                print(f"Committed {body}")
            conn.commit()
    else:
        print("No message to commit")
        sleep(5)
