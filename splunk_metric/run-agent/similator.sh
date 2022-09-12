#!/usr/bin/env bash

if [[ -z "$1" ]]; then
  PORT=7078
  echo "Using default port number $PORT"
else
  PORT=$1
  echo "Using port number $PORT"
fi

docker run --rm -p $PORT:$PORT quay.io/stackstate/simulator:latest -v record -p $PORT -t tpl.json