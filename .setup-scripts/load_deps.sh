#!/bin/bash

set -e
set -x

pip install -U pip setuptools codecov
pip install "./stackstate_checks_dev[cli]"
pip install tox-pip-version
set +x
