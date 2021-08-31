#!/bin/bash

set -e
set -x

docker login -u "$ARTIFACTORY_USER" -p "$ARTIFACTORY_PASSWORD" artifactory.stackstate.io