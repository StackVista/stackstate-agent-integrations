# Agent Check: SAP

## Overview

This check monitors [SAP][1] through the StackState Agent.

## Setup

### Installation

The SAP check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `sap.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your sap performance data.
   See the [sample sap.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

SAP include topology and metrics.

[1]: https://www.sap.com/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/sap/stackstate_checks/sap/data/conf.yaml.example
