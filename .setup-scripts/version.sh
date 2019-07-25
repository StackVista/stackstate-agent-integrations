#! /bin/bash

set -e
set -x

version=`git describe --abbrev=0`

# Try with tag, otherwise construct from scratch
if ! git describe --exact-match HEAD; then
  branch="${CI_COMMIT_REF_NAME}"
  if [ -z "${branch}" ]; then
    branch=`git symbolic-ref --short HEAD`
  fi
  #based on https://www.python.org/dev/peps/pep-0440/#version-scheme
  normalized_branch=`echo $branch | sed 's/[^a-zA-Z0-9\.]/\./g'`
  commit_count=`git rev-list --count HEAD`
  commit_hash=`git rev-parse --short HEAD | head -c 7`

  echo -n "${version}+${normalized_branch}.${commit_count}.${commit_hash}"
fi
