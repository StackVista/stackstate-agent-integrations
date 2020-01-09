# StackState Agent Integrations

This repository contains the Agent Integrations (also known as checks) that StackState officially develops and supports. 
The [StackState Agent][1] packages are equipped with all the Integrations from this repository.

# Development

Prerequisites:
- python 3.6

## Setup

To setup the environment:

    $ source .setup-scripts/setup_env.sh

From this point on the `checksdev` script is in scope and commands can be ran.

If you make any change to `checksdev`, you will need to reload it:

    $ source .setup-scripts/load_deps.sh

## Adding a check

Add a check:

    $ checksdev create <check_name>

After defining the dependencies which the check needs in `<check_name>/requirements.in` make sure to run:

    $ checksdev dep freeze

this will update the `agent_requirements.in` file to be used by the stackstate-agent build.

## Manual testing

Use the `checksdev env` command to do manual testing. Testing always happens in an environment, to list all environments run:

    $ checksdev env ls mysql

To start testing the check under local development run:

    $ checksdev env start mysql 5.7 --dev

## Automated testing

Run tests:

    $ checksdev test --cov <check_name>

You can also select specific comma-separated environments to test like so:

    $ checksdev test <check_name>:<env1>,<env2>

## CI image

The CI image is built from `.setup-scripts/image`.


[1]: https://github.com/StackVista/stackstate-agent
