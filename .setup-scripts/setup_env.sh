#!/usr/bin/env bash

# This file is meant to be sourced
# This file will pull in deps when a test is ran without the deps job having ran first.
# This happens when using the ./run_gitlab_local.sh script

export INTEGRATIONS_DIR_TMP=${CI_PROJECT_DIR:-"."}

VENV_PATH=$INTEGRATIONS_DIR_TMP/venv

if [ ! -d $VENV_PATH ]; then
  virtualenv --python=python3 $INTEGRATIONS_DIR_TMP/venv
  source $INTEGRATIONS_DIR_TMP/venv/bin/activate
  source $INTEGRATIONS_DIR_TMP/.setup-scripts/load_deps.sh
else
  pip freeze || echo '123'
  source $INTEGRATIONS_DIR_TMP/venv/bin/activate
  pip freeze
  # see if we have checksdev available, otherwise load_deps.sh
#  checksdev -h || source $INTEGRATIONS_DIR_TMP/.setup-scripts/load_deps.sh
fi

unset INTEGRATIONS_DIR_TMP
