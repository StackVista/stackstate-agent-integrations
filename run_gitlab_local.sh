#!/bin/bash

echo "Run a gitlab build step on the local machine"

if [[ $(type gitlab-runner) -eq 1 ]]; then
    echo "The cmd gilab-runner looks not available, do you want to install it ?"
    sudo wget -O /usr/local/bin/gitlab-runner https://gitlab-runner-downloads.s3.amazonaws.com/latest/binaries/gitlab-runner-linux-amd64
    sudo chmod +x /usr/local/bin/gitlab-runner
fi

gitlab-runner exec docker \
  --cache-type s3 \
  --cache-s3-server-address s3.amazonaws.com \
  --cache-s3-bucket-name ci-runner-cache-eu1 \
  --cache-s3-bucket-location eu-west-1 \
  --cache-s3-access-key $AWS_ACCESS_KEY \
  --cache-s3-secret-key $AWS_SECRET_KEY \
  --docker-volumes /var/run/docker.sock:/var/run/docker.sock \
  --env ARTIFACTORY_URL=artifactory.tooling.stackstate.io/artifactory/api/pypi/pypi-local \
  --env ARTIFACTORY_USER=$ARTIFACTORY_USER \
  --env ARTIFACTORY_PASSWORD=$ARTIFACTORY_PASSWORD \
  "$@"

