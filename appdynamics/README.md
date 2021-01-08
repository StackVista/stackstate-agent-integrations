# Agent Check: Appdynamics

## Overview

This check monitors [Appdynamics][1] through the StackState Agent.

## Setup

### Installation

The Appdynamics check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `appdynamics.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your appdynamics performance data.
   See the [sample appdynamics.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

Appdynamics does not include any metrics.

### Service Checks

Appdynamics does not include any service checks.

### Events

Appdynamics does not include any events.

### Topology

Appdynamics does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/appdynamics/stackstate_checks/appdynamics/data/conf.yaml.example
