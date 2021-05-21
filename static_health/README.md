# Agent Check: Static_health

## Overview

This check monitors Static Health ingested from CSV file through the StackState Agent.

## Setup

### Installation

The Static_health check is included in the [StackState Agent][1] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `static_health.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your static_health data.
   See the [sample static_health.d/conf.yaml][1] for all available configuration options.

2. Restart the Agent

## Data Collected

Static Health includes the health and service checks.

## Files Supported for Health 

* *CSV*


[1]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/static_health/stackstate_checks/static_health/data/conf.yaml.example
