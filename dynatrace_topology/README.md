# Agent Check: Dynatrace_topology

## Overview

This check monitors [Dynatrace][1] through the StackState Agent.

## Setup

### Installation

The Dynatrace_topology check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `dynatrace_topology.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your dynatrace_topology performance data.
   See the [sample dynatrace_topology.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Service Checks

Dynatrace_topology includes a service check.

### Events

Dynatrace_topology includes topology events.

### Topology

Dynatrace_topology includes topology.

[1]: https://www.dynatrace.com/support/help/dynatrace-api/environment-api/topology-and-smartscape/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/dynatrace_topology/stackstate_checks/dynatrace_topology/data/conf.yaml.example
