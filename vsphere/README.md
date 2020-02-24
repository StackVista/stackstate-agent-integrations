# Agent Check: VSphere

## Overview

This check monitors `Vsphere` instance through the StackState Agent.

## Setup

### Installation

The Vsphere check is included in the [StackState Agent][1] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `vsphere.d/conf.yaml` file, in the `/etc/stackstate-agent/conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your sap performance data.
   See the sample [vsphere.d/conf.yaml][1] for all available configuration options.

2. Restart the Agent

## Data Collected

Vsphere include topology and metrics.

[1]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/vsphere/stackstate_checks/vsphere/data/conf.yaml.example
