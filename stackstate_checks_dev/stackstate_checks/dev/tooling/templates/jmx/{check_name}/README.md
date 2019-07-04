# Agent Check: {check_name_cap}

## Overview

This check monitors [{check_name_cap}][1].

## Setup

### Installation

{install_info}

### Configuration

1. Edit the `{check_name}.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your {check_name} performance data.
   See the [sample {check_name}.d/conf.yaml][2] for all available configuration options.

   This check has a limit of 350 metrics per instance. The number of returned metrics is indicated in the info page.
   You can specify the metrics you are interested in by editing the configuration below. 

2. Restart the Agent

### Validation

[Run the Agent's `status` subcommand][5] and look for `{check_name}` under the Checks section.

## Data Collected

### Metrics

{check_name_cap} does not include any metrics.

### Service Checks

{check_name_cap} does not include any service checks.

### Events

{check_name_cap} does not include any events.

### Topology

{check_name_cap} does not include any topology.

[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/{check_name}/stackstate_checks/{check_name}/data/conf.yaml.example
