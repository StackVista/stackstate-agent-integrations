#!/usr/bin/env bash
# Makes the packages that exist only in the private GitLab Package Registry
# available to a local wheelhouse, and destroys the credential before returning.
#
# Why this exists (STAC-25540): vsphere pins vsphere-automation-sdk==1.82.0, an
# unmodified upstream VMware wheel that VMware withdrew from public PyPI. We
# self-host it in the GitLab Package Registry only because that org was private;
# public PyPI now serves a 0.0.1 placeholder squatting the name.
#
# This script only ever runs on events whose contents have been reviewed -- push,
# tag and workflow_dispatch. It does NOT run on pull requests, and the guard below
# enforces that independently of the workflow, because a pull request can edit the
# workflow as freely as it can edit this file. That is the actual protection for
# the credential; everything else here is defence in depth (STAC-25540, second
# review pass).
#
# The defence in depth still matters. The predecessor, setup_artifact_registry.sh,
# left a 0600 ~/.netrc in place for the remainder of the job, so every later step
# -- the tox environment, the suite's own tests, their transitive dependencies --
# could read the password. That needed no malice from anyone. Here the credential
# exists only for the duration of one pip invocation whose package set is fixed
# below, and pip is then pointed at the resulting wheelhouse so the rest of the
# job resolves offline with nothing to authenticate against.
set -euo pipefail

# A pull request must never reach the registry password, and must not be able to
# arrange for this script to fetch it one. The workflow already declines to run
# the job on pull requests; this is the same rule stated where it cannot be
# removed by editing a YAML condition.
if [ "${GITHUB_EVENT_NAME:-}" = "pull_request" ]; then
  echo "::error title=Refusing to fetch on a pull request::${0##*/} handles the private registry credential and must not run on pull_request events; the private-index suites run on the release branch instead."
  exit 1
fi

WHEELHOUSE_ARG="${1:-}"
if [ -z "${WHEELHOUSE_ARG}" ]; then
  echo "usage: ${0##*/} <wheelhouse-dir>" >&2
  exit 2
fi

# Absolute: pip.conf's find-links is resolved against the working directory of
# whichever process reads it, and tox runs pip from the suite directory.
mkdir -p "${WHEELHOUSE_ARG}"
WHEELHOUSE="$(cd "${WHEELHOUSE_ARG}" && pwd)"

# Hardcoded on purpose, and deliberately not read from the working tree. While
# the credential is on disk, a pull request must not be able to redirect pip at a
# package of its choosing.
PRIVATE_REQUIREMENTS=(
  "vsphere-automation-sdk==1.82.0"
)

for var in GITLAB_PACKAGE_REGISTRY_PYPI_SIMPLE_URL GITLAB_PACKAGE_REGISTRY_USER GITLAB_PACKAGE_REGISTRY_READONLY_PASSWORD; do
  if [ -z "${!var:-}" ]; then
    echo "::error title=Private PyPI index not configured::${var} is not available to this job, but this suite cannot resolve without the private index."
    exit 1
  fi
done

NETRC="${HOME}/.netrc"
PIP_CONF_DIR="${HOME}/.pip"

revoke_credential() {
  rm -f "${NETRC}"
}
# Covers the error paths too: a failed download must not leave the password on a
# disk that PR-authored test code goes on to run against.
trap revoke_credential EXIT

# Hostname only; the simple URL carries a path after the first '/'.
NETRC_HOST="${GITLAB_PACKAGE_REGISTRY_PYPI_SIMPLE_URL%%/*}"

umask 077
cat > "${NETRC}" <<EOF
machine ${NETRC_HOST}
login ${GITLAB_PACKAGE_REGISTRY_USER}
password ${GITLAB_PACKAGE_REGISTRY_READONLY_PASSWORD}
EOF

# A system interpreter, never the toolchain virtualenv: that venv is built by
# repository code, so invoking its pip would put a PR-controlled executable
# directly in the path of the credential.
#
# Resolved rather than hardcoded, because BCI images do not agree on a path:
# bci/python:3.13 ships /usr/bin/python3.13 and no /usr/bin/python3 at all, while
# `python3` on PATH is a /usr/local/bin shim. The workspace check below is the
# part that actually matters -- it is what makes "system" a guarantee rather than
# an assumption, whatever PATH happens to hold.
PYTHON=""
for candidate in /usr/bin/python3.13 /usr/bin/python3 /usr/local/bin/python3 "$(command -v python3 2>/dev/null || true)"; do
  if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
    PYTHON="${candidate}"
    break
  fi
done
if [ -z "${PYTHON}" ]; then
  echo "::error title=No system interpreter::Could not locate a python3 to download with."
  exit 1
fi
if [ -n "${GITHUB_WORKSPACE:-}" ]; then
  PYTHON_DIR="$(cd "$(dirname "${PYTHON}")" && pwd)"
  case "${PYTHON_DIR}/" in
    "${GITHUB_WORKSPACE%/}/"*)
      echo "::error title=Refusing a workspace interpreter::Resolved python3 at ${PYTHON}, which is inside the checkout and therefore PR-controlled."
      exit 1
      ;;
  esac
fi

echo "→ Downloading private-index packages into ${WHEELHOUSE}"
printf '    %s\n' "${PRIVATE_REQUIREMENTS[@]}"
echo "  using ${PYTHON}"

# --only-binary=:all: matters as much as the interpreter choice. Downloading an
# sdist executes its setup.py, so allowing one would hand arbitrary upstream code
# a process with the registry password readable at ~/.netrc.
"${PYTHON}" -m pip download \
  --disable-pip-version-check \
  --no-cache-dir \
  --only-binary=:all: \
  --extra-index-url "https://${GITLAB_PACKAGE_REGISTRY_PYPI_SIMPLE_URL}" \
  --dest "${WHEELHOUSE}" \
  "${PRIVATE_REQUIREMENTS[@]}"

revoke_credential
trap - EXIT

if [ -f "${NETRC}" ]; then
  echo "::error title=Credential not revoked::${NETRC} still exists after download; refusing to continue."
  exit 1
fi

# A silent miss here would fall through to public PyPI and install the 0.0.1
# placeholder, which fails much later and far less legibly.
if ! find "${WHEELHOUSE}" -maxdepth 1 -iname 'vsphere_automation_sdk-*.whl' | grep -q .; then
  echo "::error title=Private wheel missing::vsphere-automation-sdk was not downloaded into ${WHEELHOUSE}."
  exit 1
fi

# Replaces the extra-index-url that setup_artifact_registry.sh used to write.
# Nothing after this point authenticates anywhere: the private packages resolve
# from the local wheelhouse, and everything else still comes from public PyPI.
mkdir -p "${PIP_CONF_DIR}"
cat > "${PIP_CONF_DIR}/pip.conf" <<EOF
[global]
find-links = ${WHEELHOUSE}
EOF

echo " --------------------------------------------- "
echo "Wheelhouse contents:"
ls -1 "${WHEELHOUSE}"
echo
echo "Pip configuration:"
cat "${PIP_CONF_DIR}/pip.conf"
echo "Credential revoked; no ${NETRC} remains."
echo " --------------------------------------------- "
