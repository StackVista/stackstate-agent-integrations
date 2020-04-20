# Agent Check: Static_topology

## Overview

This check monitors Static Topology ingested from CSV file through the StackState Agent.

## Setup

### Installation

The Static_topology check is included in the [StackState Agent][1] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `static_topology.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your static_topology performance data.
   See the [sample static_topology.d/conf.yaml][1] for all available configuration options.

2. Restart the Agent

## Data Collected

Static Topology includes the topology and service checks.

## Files Supported for Topology 

* *CSV*


[1]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/static_topology/stackstate_checks/static_topology/data/conf.yaml.example
