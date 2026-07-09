#!/bin/sh
set -eu

max_attempts=30
attempt=1

while [ "$attempt" -le "$max_attempts" ]; do
  if uv run alembic upgrade head; then
    break
  fi

  if [ "$attempt" -eq "$max_attempts" ]; then
    echo "Alembic migrations failed after ${max_attempts} attempts." >&2
    exit 1
  fi

  echo "Alembic migration attempt ${attempt} failed; retrying in 2 seconds..." >&2
  attempt=$((attempt + 1))
  sleep 2
done

exec "$@"
