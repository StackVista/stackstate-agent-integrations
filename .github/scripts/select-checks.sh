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
#     other three splunk suites, which import its test helpers -- is not ported
#     here because no splunk suite runs yet. It lands with them in phase 2.
#   * push / workflow_dispatch run everything (GitLab: `master_branch`,
#     `release_branch`).
#
# Writes two arrays to $GITHUB_OUTPUT for `fromJson()` in a matrix:
#   checks         -- suites that need no credentials
#   private_checks -- suites that install from the private GitLab PyPI index
#
# The split is a security boundary, not a convenience. The credential-free suites
# run on GitHub-hosted runners with no secrets in scope at all, so a fork PR can
# run them safely. The private-index suites need a registry password written to
# ~/.netrc, which any test code executing afterwards can read, so they run behind
# a protected GitHub Environment that requires a human approval first (STAC-25463
# review). Keeping them in one matrix would hand that credential to every suite.

set -euo pipefail

# Suites currently running on GitHub Actions. Phase 1 is the 15 suites that need
# no Docker daemon.
#
# Deliberately NOT here yet (phase 2, needs the DinD story exercised first):
#   splunk_base, splunk_health, splunk_metric, splunk_topology
#       -- each drives a real Splunk container via docker-compose.
#   stackstate_checks_dev
#       -- its tests exercise the toolkit's own Docker helpers.
# Both public ARC runners provide a DinD sidecar, so this is a matter of proving
# it rather than provisioning anything.
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
  stackstate_checks_base
  static_health
  static_topology
  vsphere
  zabbix
)

# Suites whose requirements resolve only against the private GitLab PyPI index.
# `vsphere` pins vsphere-automation-sdk, which VMware never published to public
# PyPI (the name is squatted there by an unrelated 0.0.1 placeholder), so it is
# mirrored into the StackVista package registry and needs authentication.
#
# Everything not listed here is credential-free and must stay that way: adding a
# suite to this list moves it behind a manual approval gate, and removing the
# need for the private index is always the better fix.
PRIVATE_INDEX_CHECKS=(
  vsphere
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

is_private_index() {
  local candidate=$1 check
  for check in "${PRIVATE_INDEX_CHECKS[@]}"; do
    [ "${candidate}" = "${check}" ] && return 0
  done
  return 1
}

emit() {
  local -a selected=("$@")
  local -a public=() private=()
  local check
  for check in ${selected[@]+"${selected[@]}"}; do
    if is_private_index "${check}"; then
      private+=("${check}")
    else
      public+=("${check}")
    fi
  done

  local public_json private_json
  public_json=$(to_json ${public[@]+"${public[@]}"})
  private_json=$(to_json ${private[@]+"${private[@]}"})

  {
    echo "checks=${public_json}"
    echo "private_checks=${private_json}"
  } >>"${GITHUB_OUTPUT}"

  echo "Selected credential-free suites: ${public_json}"
  echo "Selected private-index suites:   ${private_json}"
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

emit "${SELECTED[@]+"${SELECTED[@]}"}"
