#!/usr/bin/env bash

set -x

pip install -U setuptools codecov
pip install "./stackstate_checks_dev[cli]"

set +x
