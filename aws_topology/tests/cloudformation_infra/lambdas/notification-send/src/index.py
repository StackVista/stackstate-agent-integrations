import sys
import logging
import boto3
import psycopg2

# rds settings
rds_host = os.environ.get("RDS_HOST")
rds_username = "test"
rds_user_pwd = "test"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    conn_string = "host=%s user=%s password=%s dbname=%s" % (rds_host, rds_username, rds_user_pwd, "postgres")
    conn = psycopg2.connect(conn_string)
except:
    logger.error("ERROR: Could not connect to Postgres instance.")
    sys.exit()

logger.info("SUCCESS: Connection to RDS Postgres instance succeeded")


def handler(event, context):

    query = """select id, name, job_title
            from employee
            order by 1"""

    with conn.cursor() as cur:
        rows = []
        cur.execute(query)
        for row in cur:
            rows.append(row)

    return {"statusCode": 200, "body": rows}
