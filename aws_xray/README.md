# Agent Check: AWS X-Ray

## Overview

This check monitors [AWS X-Ray Traces][1] through the StackState Agent. 
X-Ray traces are collected and send to StackState Trace Agent.

## Setup

### Installation

The AWS X-Ray check is included in the [StackState Agent][2] package, so you do not
need to install anything else on your server.

### Configuration

1. Edit the `aws_xray.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your aws performance data.
   See the [sample aws_xray.d/conf.yaml][2] for all available configuration options.

2. Restart the Agent

[1]: https://aws.amazon.com/xray/
[2]: https://github.com/StackVista/stackstate-agent-integrations/blob/master/aws/stackstate_checks/aws_xray/data/conf.yaml.example
