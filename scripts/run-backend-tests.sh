#!/bin/sh

set -eu

mode="${1:-test}"
test_database_name="scep_test"
test_database_url="postgresql+psycopg://scep:scep@localhost:5432/${test_database_name}"

case "$mode" in
    test|coverage) ;;
    *)
        echo "usage: $0 [test|coverage]" >&2
        exit 2
        ;;
esac

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_root"

postgres_was_running=$(docker compose ps --status running -q postgres)

cleanup() {
    status=$?
    trap - EXIT INT TERM
    set +e
    docker compose exec -T postgres dropdb --if-exists --force -U scep "$test_database_name" \
        >/dev/null 2>&1
    if [ -z "$postgres_was_running" ]; then
        docker compose rm --stop --force postgres >/dev/null 2>&1
    fi
    exit "$status"
}

trap cleanup EXIT INT TERM

docker compose up -d --wait postgres
docker compose exec -T postgres dropdb --if-exists --force -U scep "$test_database_name"
docker compose exec -T postgres createdb -U scep "$test_database_name"

cd backend
export DATABASE_URL="$test_database_url"
export POSTGRES_TEST_DATABASE_URL="$test_database_url"
export OTEL_SDK_DISABLED=true

uv run alembic upgrade head

if [ "$mode" = "coverage" ]; then
    uv run coverage run -m pytest
    uv run coverage report
else
    uv run pytest
fi
