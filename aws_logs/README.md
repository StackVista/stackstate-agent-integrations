# Agent Check: Aws_logs

## Overview

This check monitors [Aws_logs][1] through the StackState Agent.

## Setup

### Installation

The Aws_logs check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `aws_logs.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your aws_logs performance data.
   See the [sample aws_logs.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

Aws_logs does not include any metrics.

### Service Checks

Aws_logs does not include any service checks.

### Events

Aws_logs does not include any events.

### Topology

Aws_logs does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/aws_logs/stackstate_checks/aws_logs/data/conf.yaml.example
