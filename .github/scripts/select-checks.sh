#!/usr/bin/env bash
#
# Selects which integration check suites the test matrix should run, reproducing
# the `changes:` rules that gated each `test_<check>` job in .gitlab-ci.yml
# (GitLab -> GitHub migration, STAC-25463).
#
# GitLab evaluated a per-job `changes:` list; GitHub has no job-level path filter,
# so the equivalent is computed once here and fanned out as a matrix. This is done
# in plain git rather than a path-filter action: StackVista enforces a strict
# third-party action allowlist, and `git diff` against the merge base is exactly
# what the GitLab rule meant.
#
# Selection rules, ported from .gitlab-ci.yml:
#   * A change to a shared library, the setup scripts, or this CI wiring runs
#     EVERY suite (GitLab: the `base_changes` anchor).
#   * Otherwise only the suites whose own directory changed run.
#   * GitLab's `splunk_base_build_rule` -- a change to splunk_base also runs the
#     other three splunk suites, which import its test helpers.
#   * push / workflow_dispatch run everything (GitLab: `master_branch`,
#     `release_branch`).
#
# Writes two arrays to $GITHUB_OUTPUT for `fromJson()` in a matrix:
#   checks        -- suites that run in the shared BCI container
#   docker_checks -- suites that need a live Docker daemon and so run directly
#                    on the runner (STAC-25531)
#
# Every suite here is credential-free, and that is worth keeping. Until
# STAC-25544 `vsphere` resolved only against a private package registry, which
# meant withholding the credential from pull requests and therefore not running
# the suite on them at all -- a real coverage gap, because a `pull_request` run
# executes the pull request's own copy of the workflow and of every script it
# calls, so a run holding a secret cannot be hardened against the pull request
# that edits it. Modernising the VMware pin onto public PyPI removed the secret
# and with it the gap. If a suite ever appears to need a registry credential
# again, removing that need is the fix; splitting the matrix is not.

set -euo pipefail

# Suites currently running on GitHub Actions.
#
# Deliberately dropped, not pending:
#   postgres -- .gitlab-ci.yml carried a `test_postgres` job for a check that does
#               not exist in this repository. It is dead config, not a gap.
CHECKS=(
  agent_integration_sample
  agent_v2_integration_sample
  agent_v2_integration_stateful_sample
  agent_v2_integration_transactional_sample
  dynatrace_base
  dynatrace_health
  dynatrace_topology
  kubelet
  openmetrics
  servicenow
  splunk_base
  splunk_health
  splunk_metric
  splunk_topology
  stackstate_checks_base
  stackstate_checks_dev
  static_health
  static_topology
  vsphere
  zabbix
)

# Suites that need a real Docker daemon: the four splunk suites drive a Splunk
# container through docker-compose, and stackstate_checks_dev tests the toolkit's
# own Docker helpers (STAC-25531).
#
# These run as their own matrix directly on the runner, not inside the BCI
# container the other suites use. That is not a preference -- the tests resolve
# their target host through `get_docker_hostname()`, which reads DOCKER_HOST and
# falls back to `localhost`. Compose publishes its ports on the Docker host, so
# `localhost` is correct only when the test process shares a network namespace
# with the daemon. Inside a job container it would resolve to the container
# itself and every connection would be refused. GitLab avoided this by pointing
# DOCKER_HOST at a `docker:dind` service, whose hostname then resolved for both.
DOCKER_CHECKS=(
  splunk_base
  splunk_health
  splunk_metric
  splunk_topology
  stackstate_checks_dev
)

# splunk_health, splunk_metric and splunk_topology all build on splunk_base, so a
# change there has to run all four. Ported from the `splunk_base_build_rule`
# anchor in .gitlab-ci.yml, which added the same fan-out to every splunk job.
SPLUNK_DEPENDENTS=(
  splunk_health
  splunk_metric
  splunk_topology
)

# A change anywhere here invalidates every suite: the base classes and the test
# helpers are imported by all of them, and the setup scripts build the venv the
# suites run in.
SHARED_PATHS=(
  stackstate_checks_base/
  stackstate_checks_dev/
  stackstate_checks_tests_helper/
  .setup-scripts/
  .github/workflows/checks-tests.yml
  .github/scripts/select-checks.sh
)

to_json() {
  if [ "$#" -eq 0 ]; then
    echo "[]"
  else
    printf '%s\n' "$@" | sort -u | jq -R . | jq -c -s .
  fi
}

is_docker() {
  local candidate=$1 check
  for check in "${DOCKER_CHECKS[@]}"; do
    [ "${candidate}" = "${check}" ] && return 0
  done
  return 1
}

emit() {
  local -a selected=("$@")
  local -a public=() docker=()
  local check
  for check in ${selected[@]+"${selected[@]}"}; do
    if is_docker "${check}"; then
      docker+=("${check}")
    else
      public+=("${check}")
    fi
  done

  local public_json docker_json
  public_json=$(to_json ${public[@]+"${public[@]}"})
  docker_json=$(to_json ${docker[@]+"${docker[@]}"})

  {
    echo "checks=${public_json}"
    echo "docker_checks=${docker_json}"
  } >>"${GITHUB_OUTPUT}"

  echo "Selected credential-free suites: ${public_json}"
  echo "Selected docker-daemon suites:   ${docker_json}"
}

# Anything that is not a pull request is a full run. On the release branch the
# whole matrix is the point -- the branch should always carry a complete verdict,
# regardless of what a given commit touched -- and a manual dispatch is an
# explicit request for everything.
if [ "${EVENT_NAME}" != "pull_request" ]; then
  echo "Event '${EVENT_NAME}' is not a pull request: running every suite."
  emit "${CHECKS[@]}"
  exit 0
fi

# Diffing against the merge base keeps a stale base branch from dragging
# unrelated commits into the change set.
MERGE_BASE=$(git merge-base "origin/${BASE_REF}" HEAD)
mapfile -t CHANGED < <(git diff --name-only "${MERGE_BASE}" HEAD)

echo "Changed files (${#CHANGED[@]}) against ${BASE_REF} @ ${MERGE_BASE}:"
printf '  %s\n' "${CHANGED[@]}"

matches_prefix() {
  local file=$1 prefix
  shift
  for prefix in "$@"; do
    case "${file}" in
    "${prefix}"*) return 0 ;;
    esac
  done
  return 1
}

for file in "${CHANGED[@]}"; do
  if matches_prefix "${file}" "${SHARED_PATHS[@]}"; then
    echo "'${file}' is shared CI or library code: running every suite."
    emit "${CHECKS[@]}"
    exit 0
  fi
done

SELECTED=()
for file in "${CHANGED[@]}"; do
  for check in "${CHECKS[@]}"; do
    if [ "${file#"${check}"/}" != "${file}" ]; then
      SELECTED+=("${check}")
    fi
  done
done

# splunk_base is a library for the other three splunk suites, so pull them in
# whenever it changes. Ported from `splunk_base_build_rule` in .gitlab-ci.yml.
# `emit` sorts and de-duplicates, so adding them unconditionally is safe.
for check in ${SELECTED[@]+"${SELECTED[@]}"}; do
  if [ "${check}" = "splunk_base" ]; then
    echo "'splunk_base' changed: also running ${SPLUNK_DEPENDENTS[*]}."
    SELECTED+=("${SPLUNK_DEPENDENTS[@]}")
    break
  fi
done

emit "${SELECTED[@]+"${SELECTED[@]}"}"
