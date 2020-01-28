# Agent Check: AWS

## Overview

This check monitors [AWS][1] through the StackState Agent.

## Setup

### Installation

The Aws check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `aws.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your aws performance data.
   See the [sample aws.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

AWS does not include any metrics.

### Service Checks

AWS does not include any service checks.

### Events

AWS does not include any events.

### Topology

AWS does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/aws/stackstate_checks/aws/data/conf.yaml.example
