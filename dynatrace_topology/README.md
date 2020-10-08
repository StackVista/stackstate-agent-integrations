# Agent Check: Dynatrace Topology

## Overview

This check synchronizes [Dynatrace][1] smartscape topology through the StackState Agent. Currently supported Component Types are : 
* _Hosts_
* _Applications_
* _Processes_
* _Process-Groups_
* _Services_

## Setup

### Prerequisite

* An API Token from Dynatrace must have access to read the smartscape topology.
* Below API endpoints are used for this integration :
    * _/api/v1/entity/infrastructure/processes_
    * _/api/v1/entity/infrastructure/hosts_
    * _/api/v1/entity/applications_
    * _/api/v1/entity/infrastructure/process-groups_
    * _/api/v1/entity/services_

### Installation

The Dynatrace Topology check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `dynatrace_topology.d/conf.yaml.example` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your dynatrace performance data.
   See the [sample dynatrace_topology.d/conf.yaml.example][2] for all available configuration options.

2. Restart the Agent

## Data Collected

This integration collects topology of different component types from Dynatrace on each run. Currently, we gather all topology from the last 72 hours as per default.


[1]: https://www.dynatrace.com/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/dynatrace/stackstate_checks/dynatrace/data/conf.yaml.example
