RUNTIMETAG := $(shell date +%Y%m%d)

build:
	docker build -t stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG) .
push:
	docker push stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG)

tag_latest:
	docker tag stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG) stackstate/stackstate-agent-integrations-runner:latest

push_latest:
	docker push stackstate/stackstate-agent-integrations-runner:latest
