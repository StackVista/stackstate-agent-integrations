# Agent Check: Dynatrace Event

## Overview

This check monitors [Dynatrace][1] through the StackState Agent.

## Setup

### Installation

The Dynatrace Event check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `dynatrace_event.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your dynatrace performance data.
   See the [sample dynatrace_event.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

Dynatrace collects events.


### Topology

Dynatrace does not include any topology.

[1]: https://www.dynatrace.com/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/dynatrace_event/stackstate_checks/dynatrace_event/data/conf.yaml.example
