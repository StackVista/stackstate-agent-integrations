#!/bin/bash
echo "Docker Proxy URLs: $REGISTRY_QUAY_URL and $REGISTRY_DOCKER_URL"
docker login -u "$REGISTRY_USER" -p "$REGISTRY_PASSWORD" "$REGISTRY_HOST"
