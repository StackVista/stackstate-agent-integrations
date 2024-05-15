RUNTIMETAG := $(shell date +%Y%m%d)

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
	docker build -t stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG)-py311 .
push:
	docker push stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG)-py311

tag_latest:
	docker tag stackstate/stackstate-agent-integrations-runner:$(RUNTIMETAG)-py311 stackstate/stackstate-agent-integrations-runner:latest-py311

push_latest:
	docker push stackstate/stackstate-agent-integrations-runner:latest-py311