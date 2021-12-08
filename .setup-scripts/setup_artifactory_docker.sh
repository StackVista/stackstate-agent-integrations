#!/bin/bash
echo "Artifactory PyPI URL: $ARTIFACTORY_URL"
docker login -u "$artifactory_user" -p "$artifactory_password" "$ARTIFACTORY_URL"