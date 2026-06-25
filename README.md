# StackState Agent Integrations

This repository contains the Agent Integrations (also known as checks) that StackState officially develops and supports. 
The [StackState Agent][1] packages are equipped with all the Integrations from this repository.

For information on how to develop your own integrations, see the [developer guide on the StackState docs site][2].

# Development

Prerequisites:
- python 3 (we have a pyenv file that states a version. Leverage that.)
- bash (a working shell will do)

## Setup

To setup the environment, first export some environment variables:

    $ export GITLAB_PACKAGE_REGISTRY_USER=<your-work-email>
    $ export GITLAB_PACKAGE_REGISTRY_PYPI_SIMPLE_URL=gitlab.com/api/v4/projects/71271774/packages/pypi/simple
    $ export GITLAB_PACKAGE_REGISTRY_TOKEN=<your-gitlab-token>
    $ export GITLAB_PACKAGE_REGISTRY_PYPI_URL=gitlab.com/api/v4/projects/71271774/packages/pypi

In order to have a working setup the email you feed these environment variables should be the one you access our GitLab systems with, and the token should a personal access token with packages reading capabilities.

Then proceed to source the setup scripts to correctly load the dependencies and setup the virtual environment:

    $ source .setup-scripts/load_deps.sh
    $ source .setup-scripts/setup_env.sh

From this point on the `checksdev` script is in scope (and in the `$PATH`) and commands can be ran.

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

    $ checksdev env start mysql 5.7

## Automated testing

Run tests:

    $ checksdev test --cov <check_name>

You can also select specific comma-separated environments to test like so:

    $ checksdev test <check_name>:<env1>,<env2>
    
## Run a check

First create an agent environment:

    $ checksdev env start <check_name> <env1>
    
then you can run just once the check as you would do with a real agent:

    $ checksdev env check <check_name> <env1> [-l DEBUG]
    
You can optionally pass a log level parameter, if not passed logging is disabled. 

## CI image

The CI image is built from `.setup-scripts/image` and published to
`registry.tooling.stackstate.io` (referenced by `RUNNER_IMAGE_TAG` in
`.gitlab-ci.yml`). **Do not build or push it locally** except for ad-hoc
validation — use the GitLab CI `docker` job (build stage, manual).

Its Python **must match the CPython that the StackState Agent embeds** — the
agent's `omnibus/config/software/python3.rb` `default_version`, mirrored here in
`.python-version`. Bumping it is part of the **agent upstream-merge process**,
not ad-hoc work: see the agent repo's `UPSTREAM_MERGE.md`, section "Integrations
repo: CI runner image (embedded Python bump)".

After merging Dockerfile / Makefile changes:

1. Run the manual **`docker`** job on the pipeline (it builds from
   `python:3.13.14-bookworm` and pushes `YYYYMMDD-py313` to the registry).
2. In a follow-up commit, set `RUNNER_IMAGE_TAG` in `.gitlab-ci.yml` to the tag
   the job prints, and ensure `setup_env.sh` uses `python3.13` and
   `conda_env.ps1` defaults to `3.13.14` (must land together with the runner switch).
3. Re-run the pipeline so test jobs use the new runner.

Keeping runner Python in sync ensures CI tests run on the same interpreter the
agent ships, so version-specific bugs (e.g. pydantic validation differences) are
caught before release rather than in production.

## Dynatrace feeder
We also expose a script to feed some fake data into Dynatrace. It reads logs and metrics from inside a provided directory and shoots them to the Dynatrace API to have a reproducible setup.

To run it:

```sh
$ scripts/dynatrace_ingestion/ingest.sh scripts/dynatrace_ingestion/fixtures <instance-name> <api-key>
```

Where the `<instance-name>` is the name of the Dynatrace instance that was spinned up and the `<api-key>` is an actual API key generated from the Dynatrace interface with logs and metrics writing permissions.

### Improve this

If you find anything missing in this README please amend it! :)


[1]: https://github.com/StackVista/stackstate-agent
[2]: https://docs.stackstate.com/develop/developer-guides/agent_check/how_to_develop_agent_checks
