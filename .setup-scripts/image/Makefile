RUNTIMETAG := $(shell date +%Y%m%d)

build:
	docker build -t stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG)-py38 .
push:
	docker push stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG)-py38

tag_latest:
	docker tag stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG)-py38 stackstate/stackstate-agent-integrations-runner:latest-py38

push_latest:
	docker push stackstate/stackstate-agent-integrations-runner:latest-py38