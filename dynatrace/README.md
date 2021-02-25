# Agent Check: Dynatrace

## Overview

### Topology

This check synchronizes [Dynatrace][1] smartscape topology through the StackState Agent. Currently supported Component Types are :
* _Hosts_
* _Applications_
* _Processes_
* _Process-Groups_
* _Services_

### Events

This check gathers [Dynatrace][1] events through the StackState Agent.
Events are used to determine Health States for Health Checks in Dynatrace Stackpack.

## Setup

### Prerequisite

* An API Token from Dynatrace must have access to read the smartscape topology basically `DataExport` API value.

#### REST API Endpoints
The API Token configured in StackState Agent V2 must have access to read the topology. The permission name required for this API token is `Access problems and event feed, metrics, and topology`. The API endpoints used in the StackState Agent V2 are defined below:
* _/api/v1/entity/infrastructure/processes_
* _/api/v1/entity/infrastructure/hosts_
* _/api/v1/entity/applications_
* _/api/v1/entity/infrastructure/process-groups_
* _/api/v1/entity/services_
* _/api/vi/events_

**NOTE**
* Refer the Dynatrace documentation page on [how to create an API Token](https://www.dynatrace.com/support/help/shortlink/api-authentication#generate-a-token)
* Read the Dynatrace documentation page on [permission required for your API Token](https://www.dynatrace.com/support/help/shortlink/api-authentication#token-permissions)


### Installation

The Dynatrace Topology check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `dynatrace.d/conf.yaml.example` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your dynatrace performance data.
   See the [sample dynatrace.d/conf.yaml.example][2] for all available configuration options.

2. Restart the Agent

## Data Collected

This integration collects topology of different component types from Dynatrace on each run. Currently, we gather all topology from the last 72 hours as per default. It also collects events and evaluate the health check on the basis of number of event types for an individual EntityId(component).


[1]: https://www.dynatrace.com/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/dynatrace/stackstate_checks/dynatrace/data/conf.yaml.example
