#!/bin/bash
echo "Artifactory URL: $ARTIFACTORY_URL"
docker login -u "$artifactory_user" -p "$artifactory_password" "$ARTIFACTORY_URL"
