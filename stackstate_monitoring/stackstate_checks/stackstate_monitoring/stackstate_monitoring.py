# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base import AgentCheck, TopologyInstance

TAG_STS_CAUSALITY = "sts-causality"
TAG_STS_OBSERVABILITY = "sts-observability"
TAG_STS_DATA_INGESTION = "sts-data-ingestion"
TAG_STS_AAD = "sts-aad"

relationshipsMapping = {
    "consumer": "consumes from",
    "producer": "produces to",
    "producer-consumer": "produces to / consumes from",
    "caller": "calls",
    "user": "uses",
    "hosted": "is hosted on",
    "storage_insert": "inserts into",
}

components = {
    
    # Client
  
    "user-client": {
        "id": "user",
        "type": "user",
        "name": "User",
        "depends_on": lambda: [
            {"component": components["router-service"], "as": relationshipsMapping["caller"]},
            {"component": components["web-ui-service"], "as": relationshipsMapping["user"]},
        ],
    },
    
    "cli-client": {
        "id": "cli",
        "type": "cli",
        "name": "CLI",
        "depends_on": lambda: [
            {"component": components["router-service"], "as": relationshipsMapping["caller"]},
        ],
    },

    # Services

    "api-service": {
        "id": "api",
        "type": "service",
        "name": "API",
        "tags": {TAG_STS_CAUSALITY: None, TAG_STS_OBSERVABILITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-api-headless",
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["topology-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["elasticsearch-storage"], "as": relationshipsMapping["user"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },
    "web-ui-service": {
        "id": "ui",
        "type": "service",
        "name": "Web UI",
        "tags": {TAG_STS_CAUSALITY: None, TAG_STS_OBSERVABILITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-ui", 
        "depends_on": lambda: [
            {"component": components["router-service"], "as": relationshipsMapping["caller"]},
        ],
    },
    "view-health-service": {
        "id": "view-health",
        "type": "service",
        "name": "View Health",
        "tags": {TAG_STS_CAUSALITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-view-health",
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer-consumer"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },
    "checks-service": {
        "id": "checks",
        "type": "service",
        "name": "Checks",
        "tags": {TAG_STS_OBSERVABILITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-checks",
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["topology-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },     
    "monitors-service": {
        "id": "monitors",
        "type": "service",
        "name": "Monitors",
        "tags": {TAG_STS_CAUSALITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-checks",
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["topology-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["health-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },     
    "correlate-service": {
        "id": "correlate",
        "type": "service",
        "name": "Correlate",
        "tags": {TAG_STS_DATA_INGESTION: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-correlate", 
        "depends_on": lambda: [
            {"component": components["traces-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["connection-observations-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["topology-message-broker"], "as": relationshipsMapping["producer"]},
        ],
    },
    "state-service": {
        "id" : "state",
        "type": "service",
        "name": "State",
        "tags": {TAG_STS_CAUSALITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-state",
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["topology-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },
    "problem-producer-service": {
        "id" : "problem-producer",
        "type": "service",
        "name": "Problem Producer",
        "tags": {TAG_STS_CAUSALITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-problem-producer",
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },
    "topology-sync-service": {
        "id": "sync",
        "type": "service",
        "name": "Topology Sync",
        "tags": {TAG_STS_CAUSALITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-sync",
        "depends_on": lambda: [
            {"component": components["topology-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["topology-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },
    "topology-slicing-service": {
        "id": "slicing",
        "type": "service",
        "name": "Topology Slicing",
        "tags": {TAG_STS_CAUSALITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-slicing",
        "depends_on": lambda: [
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },
    "receiver-service": {
        "id": "receiver",
        "type": "service",
        "name": "Receiver",
        "tags": {TAG_STS_DATA_INGESTION: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-receiver",
        "depends_on": lambda: [
            {"component": components["topology-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["topology-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["traces-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["health-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["connection-observations-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["generic-events-logs-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["metrics-message-broker"], "as": relationshipsMapping["producer"]},
        ],
    },
    "health-sync-service": {
        "id": "health-sync",
        "type": "service",
        "name": "Health Sync",
        "tags": {TAG_STS_CAUSALITY: None}, 
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-health-sync",
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["producer"]},
            {"component": components["health-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },
    "aad-service": {
        "id": "spotlight",
        "type": "service",
        "name": "AAD",
        "tags": {TAG_STS_AAD: None}, 
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-anomaly-detection-spotlight-manager",
        "depends_on": lambda: [
            {"component": components["api-service"], "as": relationshipsMapping["user"]},
        ],
    },
    "router-service": {
        "id": "router",
        "type": "service",
        "name": "Router",
        "tags": {TAG_STS_OBSERVABILITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-router",
        "depends_on": lambda: [
            {"component": components["receiver-service"], "as": relationshipsMapping["caller"]},
            {"component": components["api-service"], "as": relationshipsMapping["caller"]},
        ],
    },
    "event-handler-service": {
        "id": "event-handlers",
        "type": "service",
        "name": "Event Handlers",
        "tags": {TAG_STS_CAUSALITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-view-health", 
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["stackgraph-storage"], "as": relationshipsMapping["user"]},
        ],
    },
    "e2es-service": {
        "id": "e2es",
        "type": "service",
        "name": "Events to ES",
        "tags": {TAG_STS_OBSERVABILITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-e2es",
        "depends_on": lambda: [
            {"component": components["internal-events-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["generic-events-logs-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["topology-events-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["elasticsearch-storage"], "as": relationshipsMapping["storage_insert"]},
        ],
    },
    "mm2es-service": {
        "id": "mm2es",
        "type": "service",
        "name": "Multi Metrics to ES",
        "tags": {TAG_STS_OBSERVABILITY: None}, 
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-mm2es",
        "depends_on": lambda: [
            {"component": components["metrics-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["elasticsearch-storage"], "as": relationshipsMapping["storage_insert"]},
        ],
    },
    "trace2es-service": {
        "id": "trace2es",
        "type": "service",
        "name": "Traces to ES",
        "tags": {TAG_STS_OBSERVABILITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-trace2es", 
        "depends_on": lambda: [
            {"component": components["traces-message-broker"], "as": relationshipsMapping["consumer"]},
            {"component": components["elasticsearch-storage"], "as": relationshipsMapping["storage_insert"]},
        ],
    },
    
    # Storage
      
    "stackgraph-storage": {
        "id": "stackgraph",
        "type": "storage",
        "name": "StackGraph",
        "tags": {TAG_STS_CAUSALITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-hbase-hbase-master",
    },
    "elasticsearch-storage": {
        "id": "elasticsearch",
        "type": "storage",
        "name": "ElasticSearch",
        "tags": {TAG_STS_OBSERVABILITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-elasticsearch-master",
    },
    "message-broker-storage": {
        "id": "message_broker",
        "type": "storage",
        "name": "Kafka",
        "tags": {TAG_STS_CAUSALITY: None, TAG_STS_OBSERVABILITY: None},
        "external_identifier": "urn:kubernetes:/{cluster_name}:{namespace}:service/stackstate-kafka",
    },

    # Message brokers

    "internal-events-message-broker": {
        "id": "internal-events",
        "type": "message-broker",
        "name": "Internal Events",
        "depends_on": lambda: [
            {"component": components["message-broker-storage"], "as": relationshipsMapping["hosted"]}
        ],
    },
    "traces-message-broker": {
        "id": "traces",
        "type": "message-broker",
        "name": "Traces",
        "depends_on": lambda: [
            {"component": components["message-broker-storage"], "as": relationshipsMapping["hosted"]}
        ],
    },
    "topology-events-message-broker": {
        "id": "topology-events",
        "type": "message-broker",
        "name": "Topology Events",
        "depends_on": lambda: [
            {"component": components["message-broker-storage"], "as": relationshipsMapping["hosted"]}
        ],
    },
    "topology-message-broker": {
        "id": "topology",
        "type": "message-broker",
        "name": "Topology (*)",
        "depends_on": lambda: [
            {"component": components["message-broker-storage"], "as": relationshipsMapping["hosted"]}
        ],
    },
    "health-message-broker": {
        "id": "health",
        "type": "message-broker",
        "name": "Health",
        "depends_on": lambda: [
            {"component": components["message-broker-storage"], "as": relationshipsMapping["hosted"]}
        ],
    },
    "connection-observations-message-broker": {
        "id": "connection-observations",
        "type": "message-broker",
        "name": "Connection Observations",
        "depends_on": lambda: [
            {"component": components["message-broker-storage"], "as": relationshipsMapping["hosted"]}
        ],
    },
    "generic-events-logs-message-broker": {
        "id": "generic-events-logs",
        "type": "message-broker",
        "name": "Generic Events / Logs",
        "depends_on": lambda: [
            {"component": components["message-broker-storage"], "as": relationshipsMapping["hosted"]}
        ],
    },
    "metrics-message-broker": {
        "id": "metrics",
        "type": "message-broker",
        "name": "Metrics",
        "depends_on": lambda: [
            {"component": components["message-broker-storage"], "as": relationshipsMapping["hosted"]}
        ],
    },
}


class StackstateMonitoringCheck(AgentCheck):
    # This method should also be overriden to uniquely identify your integration instance. The AgentIntegrationInstance is synchronized by the StackState Agent V2 StackPack. All topology elements produced by this check can be found by filtering on the `integration-type:{example}` and `integration-url:{instance_url}` tags in StackState for this example.
    def get_instance_key(self, instance):
        cluster_name = instance['cluster-name']
        namespace = instance['namespace']

        return TopologyInstance("self_monitoring", cluster_name + ":" + namespace)

    def external_id(self, component, suffix = ""):
        return "stackstate-{component_id}-{component_type}{suffix}".format(component_id = component["id"], component_type = component["type"], suffix = suffix)

    def blueprint_external_id(self, component):
        return self.external_id(component, "-blueprint")

    def make_tags(self, component, cluster_name, namespace):
        tags = { "cluster-name" : cluster_name, "namespace": namespace, "component": component["id"] }
        if component.get("tags") != None: 
            for key, value in component["tags"].items():
                tags[key] = value  

        return tags
    
    def tags_to_labels(self, tags): 
        labels = []
        for key, value in tags.items():
            if value is None: labels.append(key)
            else: labels.append(key + ':' + value)
        
        return labels
    
    def add_component(self, component, cluster_name, namespace):
        tags = self.make_tags(component, cluster_name, namespace)

        # Create the component
 
        blueprint_identifier = "urn:stackstate:blueprint:/{cluster_name}:{namespace}:{component_type}/{component_id}".format(cluster_name = cluster_name, namespace = namespace, component_type = component["type"], component_id = component["id"])
        blueprint_conf = {
            "name": component["name"],
            "identifiers": [blueprint_identifier],
            "labels": ["blueprint:stackstate"] + self.tags_to_labels(tags),
            "extra_tags": tags
        }

        self.component(self.blueprint_external_id(component), "{component_type}-blueprint".format(component_type = component["type"]), blueprint_conf)

        # Create relationships

        if component.get("depends_on") != None:
            for dep in component["depends_on"]():
                self.relation(self.blueprint_external_id(component), self.blueprint_external_id(dep["component"]), dep["as"], {})

        # Create the component implementation if external_identifier is provided
        
        if component.get("external_identifier") != None:
            deployment_identifier = component["external_identifier"].format(cluster_name = cluster_name, namespace = namespace)
            deployment_conf = {
                "name": component["name"],
                "identifiers": [deployment_identifier],
                "labels": ["stackstate"],
            }

            self.component(self.external_id(component), component["type"], deployment_conf)
            self.relation(self.blueprint_external_id(component), self.external_id(component), "deployed as", {})

    # check is the entry point of your agent check, `instance` is a dictionary containing the instance that was read from conf.yaml  
    def check(self, instance):
        self.log.debug("starting check for instance: %s" % instance)

        cluster_name = instance['cluster-name']
        namespace = instance['namespace']
        
        self.start_snapshot()
        
        for component in components.values(): self.add_component(component, cluster_name, namespace)

        self.stop_snapshot()

        self.log.debug("successfully ran check for instance: %s" % instance)
        