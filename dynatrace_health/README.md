# Agent Check: Dynatrace_health

## Overview

This check monitors [Dynatrace][1] Events through the StackState Agent.

## Setup

### Installation

The Dynatrace_health check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `dynatrace_health.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your dynatrace_health performance data.
   See the [sample dynatrace_health.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Events

Dynatrace_health monitors Dynatrace events and creates health stream from them.

[1]: https://www.dynatrace.com/support/help/dynatrace-api/environment-api/events-v1/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/dynatrace_health/stackstate_checks/dynatrace_health/data/conf.yaml.example
