# Agent Check: Nagios

## Overview

This check monitors [Nagios][1] through the StackState Agent.

## Setup

### Installation

The Nagios check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `nagios.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your nagios performance data.
   See the [sample nagios.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

## Data Collected

Nagios collected data include topology and metrics.

[1]: https://www.nagios.org
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/nagios/stackstate_checks/nagios/data/conf.yaml.example
