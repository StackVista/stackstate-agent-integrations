# Agent Check: Zabbix

## Overview

This check monitors [Zabbix][1] through the StackState Agent.

## Setup

### Installation

The Zabbix check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `zabbix.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your zabbix performance data.
   See the sample [zabbix.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

### Metrics

Zabbix does not include any metrics.

### Service Checks

Zabbix does not include any service checks.

### Events

Zabbix does not include any events.

### Topology

Zabbix does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/zabbix/stackstate_checks/zabbix/data/conf.yaml.example
