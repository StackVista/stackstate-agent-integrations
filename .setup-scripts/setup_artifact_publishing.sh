#!/usr/bin/env bash
set -euo pipefail

missing=
for var in GITLAB_PACKAGE_REGISTRY_PYPI_URL GITLAB_PACKAGE_REGISTRY_USER GITLAB_PACKAGE_REGISTRY_PASSWORD; do
  if [ -z "${!var}" ]; then
    missing="$missing $var"
  fi
done
if [ -n "$missing" ]; then
  echo "ERROR: Required environment variables not set:$missing" >&2
  exit 1
fi

echo "→ Configuring .pypirc for publishing to GitLab Package Registry..."

PYPI_REPOSITORY_URL="${GITLAB_PACKAGE_REGISTRY_PYPI_URL}"
if [[ "${PYPI_REPOSITORY_URL}" != http://* && "${PYPI_REPOSITORY_URL}" != https://* ]]; then
  PYPI_REPOSITORY_URL="https://${PYPI_REPOSITORY_URL}"
fi
echo "GitLab PyPI URL: ${PYPI_REPOSITORY_URL}"

# setup .pypirc
cat > ~/.pypirc <<EOF
[distutils]
index-servers =
    gitlab

[gitlab]
repository = ${PYPI_REPOSITORY_URL}
username   = $GITLAB_PACKAGE_REGISTRY_USER
password   = $GITLAB_PACKAGE_REGISTRY_PASSWORD
EOF

echo "✔ GitLab PyPI registry has been configured for publishing."