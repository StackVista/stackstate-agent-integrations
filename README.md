# StackState Agent Integrations

This repository contains the Agent Integrations (also known as checks) that StackState
officially develops and supports. The [StackState Agent][1] packages are equipped with all the Integrations from this
repository.

# Development

## Adding a check

Add a check according to the designated layout.

After adding, make sure to run

- stsdev dep freeze

to update the agent_requirements.in file to be used by the stackstate-agent build

## Manual testing

Use the `stsdev env` command to do manual testing. Testing always happens in an environment, to list all environments run

- stsdev env ls mysql

To start testing the check under local development run

- stsdev env start mysql 5.7 --dev

## CI image
The CI image is built from .gitlab-scripts/image.

## Local setup

To work on packages in this directory you can run the following:

- source .gitlab-scripts/setup_env.sh

From this point on the stsdev script is in scope and commands can be ran.

If changes are made to the stsdev, you can use .gitlab-scripts/load_deps.sh

[1]: https://github.com/StackVista/stackstate-agent
