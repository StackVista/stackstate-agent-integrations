# StackState Agent Integrations

This repository contains the Agent Integrations (also known as checks) that StackState
officially develops and supports. The [StackState Agent][1] packages are equipped with all the Integrations from this
repository.

# Development

## Testing

How to setup andvironment and run tests can be found in the .gitlab-ci.yml

## Adding a check

Add a check according to the designated layout.

After adding, make sure to run

- checksdev dep freeze

to update the agent_requirements.in file to be used by the stackstate-agent build

## Manual testing

Use the `checksdev env` command to do manual testing. Testing always happens in an environment, to list all environments run

- checksdev env ls mysql

To start testing the check under local development run

- checksdev env start mysql 5.7 --dev

## CI image
The CI image is built from .setup-scripts/image.

## Local setup

To work on packages in this directory you can run the following:

- source .setup-scripts/setup_env.sh

From this point on the checksdev script is in scope and commands can be ran.

If changes are made to the checksdev, you can use .setup-scripts/load_deps.sh

[1]: https://github.com/StackVista/stackstate-agent
