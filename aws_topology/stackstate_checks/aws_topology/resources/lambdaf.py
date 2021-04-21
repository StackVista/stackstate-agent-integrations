import time
from botocore.exceptions import ClientError
from .utils import make_valid_data
from .registry import RegisteredResourceCollector


class LambdaCollector(RegisteredResourceCollector):
    API = "lambda"
    COMPONENT_TYPE = "aws.lambda"
    MEMORY_KEY = "lambda_func"

    def process_all(self):
        lambda_func = {}
        for page in self.client.get_paginator('list_functions').paginate():
            for function_data_raw in page.get('Functions') or []:
                function_data = make_valid_data(function_data_raw)
                result = self.process_lambda(function_data)
                lambda_func.update(result)
        return lambda_func

    def process_lambda(self, function_data):
        function_arn = function_data['FunctionArn']
        function_name = function_data['FunctionName']
        function_tags = None
        while function_tags is None:
            try:
                function_tags = self.client.list_tags(Resource=function_arn).get('Tags') or []
            except ClientError as exception_obj:
                if exception_obj.response['Error']['Code'] == 'ThrottlingException':
                    time.sleep(4)
                    pass
        function_data['Tags'] = function_tags
        self.agent.component(function_arn, self.COMPONENT_TYPE, function_data)
        lambda_vpc_config = function_data.get('VpcConfig')
        vpc_id = None
        if lambda_vpc_config:
            vpc_id = lambda_vpc_config['VpcId']
            if vpc_id:
                self.agent.relation(function_arn, vpc_id, 'uses service', {})
            self.agent.create_security_group_relations(function_arn, lambda_vpc_config, 'SecurityGroupIds')

        for alias_data in self.client.list_aliases(FunctionName=function_arn).get('Aliases') or []:
            alias_data['Function'] = function_data
            alias_arn = alias_data['AliasArn']
            self.agent.component(alias_arn, 'aws.lambda.alias', alias_data)
            if vpc_id:
                self.agent.relation(alias_arn, vpc_id, 'uses service', {})
        return {function_name: function_arn}
