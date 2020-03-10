# (C) Datadog, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json

from stackstate_checks.base import AgentCheck, ConfigurationError, TopologyInstance
from .util import create_resource_arn


class CapitalOneCheck(AgentCheck):
    INSTANCE_TYPE = "capital-one"
    SERVICE_CHECK_NAME = 'Capital-One'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.url = None

    def get_instance_key(self, instance):
        if 'url' not in instance:
            raise ConfigurationError('Missing url in topology instance configuration.')

        instance_url = instance['url']
        return TopologyInstance(self.INSTANCE_TYPE, instance_url)

    def location_info(self, account_id, region):
        return {'Location': {'AwsAccount': account_id, 'AwsRegion': region}}

    def check(self, instance):
        file_path = instance.get("url")
        self.start_snapshot()
        try:
            # open the file from where to read the topology
            with open(file_path, 'r') as f:
                # the file contains json data in each line, so process data each line and create topology
                for line in f.readlines():
                    self.parse_topology(line)
        except Exception as err:
            msg = 'Capital One check failed: {}'.format(str(err))
            self.log.error(msg)
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=msg, tags=self.tags)
        finally:
            self.stop_snapshot()

    def parse_topology(self, data):
        """
        Create the topology from JSON data on the basis of different service types
        :param data: the JSON data of a line from the file
        :return: None
        """
        json_response = json.loads(data)
        service_type = json_response.get("serviceType")
        if service_type == "Ec2":
            self.process_ec2(json_response)

    def process_ec2(self, json_response):
        """
        Create topology for EC2, VPC and Subnet from the json data
        :param json_response:
        :return: None
        """
        instance_id = json_response.get("instanceId")
        ec2_data = json_response.get("ec2Attributes")
        account = ec2_data.get("accountNumber")
        region = json_response.get("region")
        domain = "{}:{}".format(account, region)
        ec2_data["domain"] = domain
        ec2_data.update(self.location_info(account, region))
        self.process_vpc(ec2_data, region)
        self.component(instance_id, "ec2", ec2_data)
        if ec2_data.get('subnetId'):
            self.relation(instance_id, ec2_data['subnetId'], 'uses service', {})

    def process_vpc(self, vpc_data, region):
        """
        Create the topology for VPC and subnet in this subtask from main process_ec2
        :param vpc_data: the VPC json data to process from
        :param region: the region of service type data
        :return: None
        """

        # process VPC
        vpc_description = {}
        account = vpc_data.get("accountNumber")
        domain = "{}:{}".format(account, region)
        vpc_id = vpc_data.get('vpcId')
        vpc_description.update(self.location_info(account, region))
        vpc_description['URN'] = [
            create_resource_arn('ec2', region, account, 'vpc', vpc_id)
        ]
        vpc_description['vpcId'] = vpc_id
        vpc_description['Domain'] = domain
        self.component(vpc_id, 'aws.vpc', vpc_description)

        # process Subnets
        subnet_description = {}
        subnet_id = vpc_data['subnetId']
        subnet_description.update(self.location_info(account, region))
        subnet_description['URN'] = [
            create_resource_arn('ec2', region, account, 'subnet', subnet_id)
        ]
        subnet_description['subnetId'] = subnet_id
        subnet_description['Domain'] = domain
        self.component(subnet_id, 'aws.subnet', subnet_description)
        self.relation(subnet_id, vpc_id, 'uses service', {})
