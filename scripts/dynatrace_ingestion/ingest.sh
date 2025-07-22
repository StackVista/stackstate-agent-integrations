#!/bin/bash

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <directory> <environment-id> <api-token>"
  exit 1
fi

METRICS_DIRECTORY="$1/metrics"
LOGS_DIRECTORY="$1/logs"
ENVIRONMENT_ID="$2"
API_TOKEN="$3"
METRICS_INGESTION_URL="https://$ENVIRONMENT_ID.live.dynatrace.com/api/v2/metrics/ingest"
LOGS_INGESTION_URL="https://$ENVIRONMENT_ID.live.dynatrace.com/api/v2/logs/ingest"

for file in "$METRICS_DIRECTORY"/*.txt; do
  if [[ -f "$file" ]]; then
    printf "Sending file: ${file}\n"

    # Send the file as payload
    curl -X POST "$METRICS_INGESTION_URL" \
      -H 'Accept: application/json; charset=utf-8' \
      -H "Authorization: Api-Token $API_TOKEN" \
      -H "Content-Type: text/plain; charset=utf-8" \
      -d @"$file"

    printf "\n\nFile sent: ${file}\n"
  else
    printf "No txt files found in the directory."
  fi
done

for file in "$LOGS_DIRECTORY"/*.json; do
  if [[ -f "$file" ]]; then
    printf "Sending file: ${file}\n"

    # Send the file as payload
    curl -X POST "$LOGS_INGESTION_URL" \
      -H 'Accept: application/json; charset=utf-8' \
      -H "Authorization: Api-Token $API_TOKEN" \
      -H "Content-Type: application/json; charset=utf-8" \
      -d @"$file"

    printf "\n\nFile sent: ${file}\n"
  else
    printf "No txt files found in the directory."
  fi
done
