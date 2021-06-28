import json
import logging
import os
import random

import boto3
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch
from boto3.dynamodb.conditions import Key

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

test_region = os.environ['AWS_REGION']
patch(['boto3'])
lambda_client = boto3.client('lambda', region_name=test_region)


def lambda_handler(event, context):
    logger.info('## EVENT')
    logger.info(event)

    error_span = event.get("error")
    if error_span:
        return produce_error_span(error_span["code"], error_span["message"])

    list_lambdas()
    call_lambda(event)
    item_writen = do_something()

    return item_writen


@xray_recorder.capture('produce_error')
def produce_error_span(code, msg):
    return {
        'statusCode': code,
        'body': json.dumps({'message': msg})
    }


@xray_recorder.capture('add_item_to_book_table')
def do_something():
    dynamo_db = boto3.resource('dynamodb', region_name=test_region)
    table = dynamo_db.Table('Book')
    resp = table.query(KeyConditionExpression=Key('Author').eq('Douglas Adams'))
    if len(resp['Items']) == 0:
        with table.batch_writer() as batch:
            batch.put_item(Item={'Author': 'Douglas Adams',
                                 'Title': "The Hitchhiker 's Guide to the Galaxy",
                                 'Category': 'Science fiction',
                                 'Formats': {'Hardcover': 'GVJZQ7JK',
                                             'Paperback': 'A4TFUR98',
                                             'Audiobook': 'XWMGHW96'}
                                 })
        item_writen = True
        msg = 'Item writen'
    else:
        item_writen = False
        msg = 'Item in table'

    xray_recorder.current_subsegment().put_annotation('add_item_to_book_table', msg)
    return item_writen


@xray_recorder.capture('list_lambdas')
def list_lambdas():
    funcs = lambda_client.list_functions()
    msg = 'num of functions {}'.format(len(funcs['Functions']))
    logger.info(msg)
    xray_recorder.current_subsegment().put_annotation('list_lambdas', msg)


def call_lambda(event):
    response = lambda_client.invoke(FunctionName='TestDeleteTrace', InvocationType='RequestResponse',
                                    Payload=json.dumps(event))
    payload = response['Payload'].read()
    logger.info(payload)