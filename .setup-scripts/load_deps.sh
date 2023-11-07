#!/usr/bin/env bash

set -x

pip3 install "./stackstate_checks_dev[cli]"
pip3 install tox-pip-version
set +x
