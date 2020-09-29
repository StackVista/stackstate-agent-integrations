# Agent Check: Dynatrace Topology

## Overview

This check monitors [Dynatrace][1] smartscape topology through the StackState Agent.

## Setup

### Installation

The Dynatrace Topology check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `dynatrace.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your dynatrace performance data.
   See the [sample dynatrace.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

Dynatrace collects topology.

[1]: https://www.dynatrace.com/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/dynatrace/stackstate_checks/dynatrace/data/conf.yaml.example
