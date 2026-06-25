RUNTIMETAG := $(shell date +%Y%m%d)
PYTHON_SUFFIX := py313
IMAGE_REPO ?= stackstate/stackstate-agent-integrations-runner
# CI `docker` job overrides with python:3.13.14-bookworm (docker.io login); local default is the mirror.
PYTHON_BASE_IMAGE ?= registry.tooling.stackstate.io/docker/python:3.13.14-bookworm
include ../python_tool_versions.env
export

#build:
#	docker build -t stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG) .
#push:
#	docker push stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG)
#
#tag_latest:
#	docker tag stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG) stackstate/stackstate-agent-integrations-runner:latest
#
#push_latest:
#	docker push stackstate/stackstate-agent-integrations-runner:latest

# ^^^ Old runner
# ----------------------------------------------
# vvv New runner

build:
	docker build --build-arg PYTHON_BASE_IMAGE=$(PYTHON_BASE_IMAGE) \
		--build-arg PIP_VERSION=$(PIP_VERSION) \
		--build-arg SETUPTOOLS_VERSION=$(SETUPTOOLS_VERSION) \
		-t $(IMAGE_REPO):$(RUNTIMETAG)-$(PYTHON_SUFFIX) .

push:
	docker push $(IMAGE_REPO):$(RUNTIMETAG)-$(PYTHON_SUFFIX)

tag_latest:
	docker tag $(IMAGE_REPO):$(RUNTIMETAG)-$(PYTHON_SUFFIX) $(IMAGE_REPO):latest-$(PYTHON_SUFFIX)

push_latest:
	docker push $(IMAGE_REPO):latest-$(PYTHON_SUFFIX)

# Print the tag CI should set as RUNNER_IMAGE_TAG after a successful publish.
print_tag:
	@echo $(RUNTIMETAG)-$(PYTHON_SUFFIX)
