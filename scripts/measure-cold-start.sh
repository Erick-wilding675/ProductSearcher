#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
LIMIT_SECONDS="2"

measure() {
  local name="$1"
  local path="$2"

  local time
  time=$(curl -sS -o /dev/null -w "%{time_total}" "${BASE_URL}${path}")

  echo "${name}: ${time}s"

  if awk -v t="$time" -v limit="$LIMIT_SECONDS" 'BEGIN { exit !(t < limit) }'; then
    echo "PASS: ${name} respondeu em menos de ${LIMIT_SECONDS}s."
  else
    echo "FAIL: ${name} excedeu o limite de ${LIMIT_SECONDS}s."
    return 1
  fi
}

echo "Medindo primeira requisição para ${BASE_URL}"
echo

measure "health" "/health"
measure "search" "/search?q=notebook"
