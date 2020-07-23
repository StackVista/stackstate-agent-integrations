# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# project
from stackstate_checks.base import AgentCheck, MetricStream, MetricHealthChecks
import time
from random import seed
from random import randint

seed(1)


class AgentIntegrationSampleCheck(AgentCheck):

    def check(self, instance):
        # gets the value of the `url` property
        instance_url = instance['url']
        # gets the value of the `default_timeout` property or defaults to 5
        default_timeout = self.init_config.get('default_timeout', 5)
        # gets the value of the `timeout` property or defaults `default_timeout` and casts it to a float data type
        timeout = float(instance.get('timeout', default_timeout))

        self.component("urn:example/host:this_host", "Host", {
            "name": "this-host",
            "domain": "Webshop",
            "layer": "Hosts",
            "identifiers": ["another_identifier_for_this_host"],
            "labels": ["host:this_host", "region:eu-west-1"],
            "environment": "Production"
        })

        some_application_cpu_usage = MetricStream("Host CPU Usage", "host.cpu.usage",
                                                  conditions={"hostname": "this-host"},
                                                  unit_of_measure="Percentage",
                                                  aggregation="MEAN",
                                                  priority="HIGH")
        some_application_cpu_usage.identifier()
        cpu_max_average_check = MetricHealthChecks.maximum_average(some_application_cpu_usage.identifier(),
                                                                   "Max CPU Usage", 75, 90)
        self.component("urn:example/application:some_application", "Application",
                       data={
                            "name": "some-application",
                            "domain": "Webshop",
                            "layer": "Applications",
                            "identifiers": ["another_identifier_for_some_application"],
                            "labels": ["application:some_application", "region:eu-west-1", "hosted_on:this-host"],
                            "environment": "Production",
                            "version": "0.2.0"
                       },
                       streams=[some_application_cpu_usage],
                       checks=[cpu_max_average_check])

        self.relation("urn:example/application:some_application", "urn:example/host:this_host", "IS_HOSTED_ON", {})

        self.gauge("host.cpu.usage", randint(0, 100), tags=["hostname:this-host"])

        self.event({
            "timestamp": int(time.time()),
            "source_type_name": "HTTP_TIMEOUT",
            "msg_title": "URL timeout",
            "msg_text": "Http request to %s timed out after %s seconds." % (instance_url, timeout),
            "aggregation_key": "instance-request-%s" % instance_url
        })

        # some logic here to test our connection and if successful:
        self.service_check("example.can_connect", AgentCheck.OK, tags=["instance_url:%s" % instance_url])
