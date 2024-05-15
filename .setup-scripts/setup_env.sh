#!/usr/bin/env bash

set -x

# This file is meant to be sourced
# This file will pull in deps when a test is ran without the deps job having ran first.
# This happens when using the ./run_gitlab_local.sh script

export INTEGRATIONS_DIR_TMP=${CI_PROJECT_DIR:-"."}

VENV_PATH=$INTEGRATIONS_DIR_TMP/venv

if [ ! -d $VENV_PATH ]; then
  echo "$VENV_PATH doesn't exist, create the venv and loading deps"
  virtualenv --python=python3.11 --pip=24.0 $INTEGRATIONS_DIR_TMP/venv
  source $INTEGRATIONS_DIR_TMP/venv/bin/activate
  pip install pylint==2.17.2
  pip install docker==6.1.3
  pip install 'cython<3.0.0'
  pip install "pyyaml==5.4.1" --no-build-isolation
  pip install --upgrade pip setuptools wheel
  source $INTEGRATIONS_DIR_TMP/.setup-scripts/load_deps.sh
else
  echo "$VENV_PATH already exists, only activating the venv"
  ls $INTEGRATIONS_DIR_TMP/venv/bin || echo 'no bin'
  ls $INTEGRATIONS_DIR_TMP/venv/lib/python3.11/site-packages || echo 'no site-packages'
  source $INTEGRATIONS_DIR_TMP/venv/bin/activate
  pip install pylint==2.17.2
  pip install docker==6.1.3
  pip freeze
  pip -V
  checksdev -h || source $INTEGRATIONS_DIR_TMP/.setup-scripts/load_deps.sh
fi

unset INTEGRATIONS_DIR_TMP
set +x
