#!/usr/bin/env bash

set -x

pip install --disable-pip-version-check -U pip setuptools codecov
pip install "./stackstate_checks_dev[cli]"
set +x
