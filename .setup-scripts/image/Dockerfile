# Match agent embedded CPython 3.13.14. Docker Hub publishes 3.13.14 on bookworm, not bullseye.
# CI `docker` job passes PYTHON_BASE_IMAGE=python:3.13.14-bookworm (docker.io is logged in there).
ARG PYTHON_BASE_IMAGE=registry.tooling.stackstate.io/docker/python:3.13.14-bookworm
FROM ${PYTHON_BASE_IMAGE}
ARG PIP_VERSION=24.3.1
ARG SETUPTOOLS_VERSION=75.8.2
RUN apt-get update && \
    apt-get install -y apt-transport-https ca-certificates curl gnupg2 lsb-release && \
    apt-get clean && \
    pip3 install "pip==${PIP_VERSION}" "setuptools==${SETUPTOOLS_VERSION}" virtualenv codecov wheel

RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io && \
    apt-get clean

RUN curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose
