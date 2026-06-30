#!/usr/bin/env bash

set -x

# This file is meant to be sourced
# This file will pull in deps when a test is ran without the deps job having ran first.
# This happens when using the ./run_gitlab_local.sh script

export INTEGRATIONS_DIR_TMP=${CI_PROJECT_DIR:-"."}
SETUP_SCRIPTS_DIR="${INTEGRATIONS_DIR_TMP}/.setup-scripts"
# shellcheck source=python_tool_versions.env
source "${SETUP_SCRIPTS_DIR}/python_tool_versions.env"

VENV_PATH=$INTEGRATIONS_DIR_TMP/venv

if [ ! -d $VENV_PATH ]; then
  echo "$VENV_PATH doesn't exist, create the venv and loading deps"
  python3.13 -m venv $INTEGRATIONS_DIR_TMP/venv
  source $INTEGRATIONS_DIR_TMP/venv/bin/activate
  pip install "pip==${PIP_VERSION}" "setuptools==${SETUPTOOLS_VERSION}" wheel
  pip install pylint==2.17.2
  pip install docker==6.1.3
  pip install 'cython<3.0.0'
  pip install "pyyaml==6.0.1" --no-build-isolation
  source $INTEGRATIONS_DIR_TMP/.setup-scripts/load_deps.sh
else
  echo "$VENV_PATH already exists, only activating the venv"
  ls $INTEGRATIONS_DIR_TMP/venv/bin || echo 'no bin'
  ls $INTEGRATIONS_DIR_TMP/venv/lib/python3.13/site-packages || echo 'no site-packages'
  source $INTEGRATIONS_DIR_TMP/venv/bin/activate
  pip install pylint==2.17.2
  pip install docker==6.1.3
  pip freeze
  pip -V
  checksdev -h || source $INTEGRATIONS_DIR_TMP/.setup-scripts/load_deps.sh
fi

unset INTEGRATIONS_DIR_TMP
set +x
