#!/usr/bin/env bash

set -x

export INTEGRATIONS_DIR_TMP=${CI_PROJECT_DIR:-"."}
export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8

source /Users/mvaneeden/opt/anaconda3/etc/profile.d/conda.sh
conda activate stackstate-agent-integrations || conda create --name stackstate-agent-integrations python=3.6
conda activate stackstate-agent-integrations

checksdev -h || source .setup-scripts/load_deps.sh

checksdev test --cov agent_integration_sample