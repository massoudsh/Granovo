#!/bin/sh
# Initialize the schema, then hand off to the container command.
set -eu

if [ "${GRANOVO_SKIP_DB_INIT:-0}" != "1" ]; then
  attempts="${GRANOVO_DB_INIT_ATTEMPTS:-30}"
  delay="${GRANOVO_DB_INIT_DELAY:-2}"
  i=1
  while :; do
    if python -m backend.db; then
      break
    fi
    if [ "$i" -ge "$attempts" ]; then
      echo "granovo: database initialization failed after ${attempts} attempts" >&2
      exit 1
    fi
    echo "granovo: database not ready (attempt ${i}/${attempts}); retrying in ${delay}s" >&2
    i=$((i + 1))
    sleep "$delay"
  done
fi

exec "$@"
