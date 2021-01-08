# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import logging

import requests
from schematics import Model
from schematics.types import URLType, StringType

from stackstate_checks.checks import AgentCheck, StackPackInstance


class InstanceInfo(Model):
    url = URLType(required=True)
    user = StringType(required=True)
    password = StringType(required=True)


class AppDynamicsCheck(AgentCheck):
    INSTANCE_TYPE = 'appdynamics'
    SERVICE_CHECK_NAME = "appdynamics.topology_information"
    INSTANCE_SCHEMA = InstanceInfo

    def get_instance_key(self, instance_info):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance_info.url))

    def check(self, instance_info):
        try:
            client = AppDynamicsClient(instance_info)
            self.start_snapshot()
            self._process_components(client)
            self._process_relations(client)
            self.stop_snapshot()
            msg = 'AppDynamics instance detected at %s ' % instance_info.url
            tags = ['url:%s' % instance_info.url]
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=tags, message=msg)
        except Exception as e:
            self.log.exception(e)
            msg = '%s: %s' % (type(e).__name__, str(e))
            self.service_check(
                self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=msg, tags=instance_info.instance_tags
            )

    def _process_components(self, client):
        apps = client.get_data('/')
        for app in apps:
            business_transactions = client.get_data('/%s/business-transactions' % app['name'])
            tiers = client.get_data('/%s/tiers' % app['name'])
            backends = client.get_data('/%s/backends' % app['name'])
            nodes = client.get_data('/%s/nodes' % app['name'])

    def _process_relations(self, client):
        pass


class AppDynamicsClient:
    def __init__(self, instance_info):
        self.log = logging.getLogger(__name__)
        self.url = instance_info.url
        self.user = instance_info.user
        self.password = instance_info.password

    def get_data(self, path, params=None):
        request_url = '%s/controller/rest/applications%s' % self.url, path
        payload = {'output': 'JSON'}
        if params:
            payload.update(params)
        r = requests.get(request_url, auth=(self.user, self.password), params=payload)
        if r.status_code == 200:
            result = r.json()
            self.log.info('Retrieving data from path: %s count: %d' % path, len(result))
            return result
        else:
            raise AppDynamicsClientException('ERROR! path: %s status_code: %s' % request_url, r.status_code)


class AppDynamicsClientException(Exception):
    pass
