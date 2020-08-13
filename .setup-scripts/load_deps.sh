#!/usr/bin/env bash

set -x

pip install -U setuptools codecov
pip install "./stackstate_checks_dev[cli]"
pip install pip==19.3.1
set +x
