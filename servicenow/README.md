# Agent Check: ServiceNow

## Overview

This check monitors [ServiceNow][1] through the StackState Agent.

## Setup

### Installation

The ServiceNow check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `servicenow.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your servicenow performance data.
   See the [sample servicenow.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

Servicenow includes the topology and service checks.

[1]: https://www.servicenow.com/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/servicenow/stackstate_checks/servicenow/data/conf.yaml.example
