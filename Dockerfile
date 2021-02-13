FROM docker.io/stackstate/stackstate-agent-2:2.9.0
COPY servicenow/stackstate_checks/servicenow/data/conf.yaml /etc/stackstate-agent/conf.d/servicenow.d/conf.yaml
COPY agent_integration_sample/stackstate_checks/agent_integration_sample/data/conf.yaml /etc/stackstate-agent/conf.d/agent_integration_sample.d/conf.yaml
