#!/bin/bash

HOST="docker"
PORT="2375"
TIMEOUT=120 # Total time to wait in seconds

echo "Waiting for Docker service on $HOST:$PORT (Timeout: ${TIMEOUT}s)..."

START_TIME=$SECONDS
while ! nc -z $HOST $PORT >/dev/null 2>&1; do

  ELAPSED=$(( SECONDS - START_TIME ))
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "\nError: Timed out after ${TIMEOUT}s waiting for Docker service."
    exit 1
  fi

  echo -n "."
  sleep 1
done

echo "\nDocker service is up!"
exit 0