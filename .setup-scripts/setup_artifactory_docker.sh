#!/bin/bash

echo ARTIFACTORY_URL: "$ARTIFACTORY_URL"
echo artifactory_url: "$artifactory_url"
docker login -u "$ARTIFACTORY_USER" -p "$ARTIFACTORY_PASSWORD" "$ARTIFACTORY_URL"