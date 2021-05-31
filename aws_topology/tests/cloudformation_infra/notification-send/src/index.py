import sys
import logging
import os
import json
import boto3
import psycopg2

secretsmanager = boto3.client("secretsmanager")
secret = json.loads(secretsmanager.get_secret_value(SecretId=os.environ.get("SECRET")).get("SecretString"))

# rds settings
rds_host = os.environ.get("RDS_HOST")
rds_username = secret.get("username")
rds_user_pwd = secret.get("password")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

try:
    conn = psycopg2.connect(f"host={rds_host} user={rds_username} password={rds_user_pwd} dbname=postgres")
except:
    logger.error("ERROR: Could not connect to Postgres instance.")
    sys.exit(1)

logger.info("SUCCESS: Connection to RDS Postgres instance succeeded")


def handler(event, context):
    logger.debug(event)
    payload = event.get("Input")
    name_list = payload.get("recipients")

    query = """select name, email
            from mailing_list
            where name in %(name_list)s"""

    with conn.cursor() as cur:
        contacts = []
        cur.execute(query, {"name_list": tuple(name_list)})
        for row in cur:
            contacts.append({"name": row[0], "email": row[1]})

    logger.debug(contacts)
    return contacts
