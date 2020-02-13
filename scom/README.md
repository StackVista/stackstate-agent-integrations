# Agent Check: Scom

## Overview

This check monitors [Scom][1] through the StackState Agent.

## Setup

### Installation

The Scom check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `scom.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your scom performance data.
   See the [sample scom.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

Scom does not include any metrics.

### Service Checks

Scom does not include any service checks.

### Events

Scom does not include any events.

### Topology

Scom does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/scom/stackstate_checks/scom/data/conf.yaml.example
