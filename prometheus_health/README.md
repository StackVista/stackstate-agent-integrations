# Agent Check: prometheus-health

## Overview

This check generates StackState health states based on prometheus alerting rules that are firing. Any rule that is
firing is converted into a Critical health state in StackState.

At the moment it is focused at Prometheus running inside Kubernets and it is only aligned with the topology
from the Kubernetes StackPack and the Kubernets agent.

## Setup

### Installation

The prometheus-health check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `prometheus_health.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your prometheus_health performance data.
   See the [sample prometheus_health.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

prometheus-health does not include any metrics.

### Service Checks

prometheus-health does not include any service checks.

### Events

prometheus-health does not include any events.

### Topology

prometheus-health does not include any topology.

### Health state
Firing Prometheus alerting rules are converted to critical StackState Health states.

[1]: https://prometheus.io
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/prometheus_health/stackstate_checks/prometheus_health/data/conf.yaml.example
