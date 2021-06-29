from __future__ import print_function
import json
import os
import boto3
from aws_xray_sdk.core import xray_recorder, patch
from boto3.dynamodb.conditions import Key

test_region = os.environ['AWS_REGION']


def lambda_handler(event, context):
    print(json.dumps(event))

    msg = delete_item_from_table()

    return {
        'statusCode': 200,
        'body': json.dumps({'message': msg})
    }


@xray_recorder.capture('delete_item_from_table')
def delete_item_from_table():
    dynamo_db = boto3.resource('dynamodb', region_name=test_region)
    table = dynamo_db.Table('Book')
    resp = table.query(KeyConditionExpression=Key('Author').eq('Douglas Adams'))
    if len(resp) != 0:
        table.delete_item(Key={'Author': 'Douglas Adams', 'Title': "The Hitchhiker 's Guide to the Galaxy"})
        item_deleted = True
        msg = 'item deleted'
    else:
        item_deleted = False
        msg = 'item not found'
    xray_recorder.current_subsegment().put_annotation('delete_item_from_table', msg)
    return msg