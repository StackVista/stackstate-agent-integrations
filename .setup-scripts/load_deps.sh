#!/usr/bin/env bash

set -x

pip install -U pip setuptools codecov
pip install "./stackstate_checks_dev[cli]"

set +x
