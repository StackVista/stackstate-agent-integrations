#!/usr/bin/env bash
set -euo pipefail

echo "→ Configuring pip to pull from GitLab Package Registry (simple URL)..."
echo "GitLab PyPI simple URL: $GITLAB_PACKAGE_REGISTRY_PYPI_SIMPLE_URL"

# setup pip.conf
mkdir -p ~/.pip
cat > ~/.pip/pip.conf <<EOF
[global]
extra-index-url = https://$GITLAB_PACKAGE_REGISTRY_USER:$GITLAB_PACKAGE_REGISTRY_TOKEN@$GITLAB_PACKAGE_REGISTRY_PYPI_SIMPLE_URL
EOF