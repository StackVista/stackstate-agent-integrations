# Agent Check: Openmetrics

## Overview

This check monitors [Openmetrics][1] through the StackState Agent.

## Setup

### Installation

The Openmetrics check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `openmetrics.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your openmetrics performance data.
   See the [sample openmetrics.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

Openmetrics does not include any metrics.

### Service Checks

Openmetrics does not include any service checks.

### Events

Openmetrics does not include any events.

### Topology

Openmetrics does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/openmetrics/stackstate_checks/openmetrics/data/conf.yaml.example
