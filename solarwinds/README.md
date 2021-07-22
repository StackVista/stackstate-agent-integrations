# Agent Check: Solarwinds

## Overview

This check monitors [Solarwinds][1] through the StackState Agent.

## Setup

### Installation

The Solarwinds check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `solarwinds.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your solarwinds performance data.
   See the [sample solarwinds.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

Solarwinds does not include any metrics.

### Service Checks

Solarwinds does not include any service checks.

### Events

Solarwinds does not include any events.

### Topology

Solarwinds does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/solarwinds/stackstate_checks/solarwinds/data/conf.yaml.example
