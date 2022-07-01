# Agent Check: stackstate-monitoring

## Overview

This check monitors [stackstate-monitoring][1] through the StackState Agent.

## Setup

### Installation

The stackstate-monitoring check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `stackstate_monitoring.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your stackstate_monitoring performance data.
   See the [sample stackstate_monitoring.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

stackstate-monitoring does not include any metrics.

### Service Checks

stackstate-monitoring does not include any service checks.

### Events

stackstate-monitoring does not include any events.

### Topology

stackstate-monitoring does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/stackstate_monitoring/stackstate_checks/stackstate_monitoring/data/conf.yaml.example
