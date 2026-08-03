#!/usr/bin/env bash

set -euo pipefail

SMOKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(cd "$SMOKE_DIR/.." && pwd)"
REPOSITORY_ROOT="$(cd "$ENGINE_DIR/.." && pwd)"
SMOKE_ENV_FILE="${SMOKE_ENV_FILE:-$SMOKE_DIR/.env}"

if [[ -f "$SMOKE_ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$SMOKE_ENV_FILE"
  set +a
fi

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
SMOKE_RUNTIME_DIR="${SMOKE_RUNTIME_DIR:-$SMOKE_DIR/runtime}"
umask 077
mkdir -p "$SMOKE_RUNTIME_DIR"
chmod 700 "$SMOKE_RUNTIME_DIR"

SMOKE_STATE_FILE="$SMOKE_RUNTIME_DIR/state.json"
SMOKE_CREDENTIALS_FILE="$SMOKE_RUNTIME_DIR/credentials.env"
SMOKE_SCENARIO_FILE="$SMOKE_RUNTIME_DIR/scenario.json"
SMOKE_DRAFT_BOOTSTRAP_FILE="$SMOKE_RUNTIME_DIR/bootstrap-draft.json"
SMOKE_BOOTSTRAP_FILE="$SMOKE_RUNTIME_DIR/bootstrap.json"
SMOKE_CHECKPOINT_FILE="$SMOKE_RUNTIME_DIR/checkpoint.json"
SMOKE_REPORT_FILE="$SMOKE_RUNTIME_DIR/report.json"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

require_value() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Required setting is empty: $name" >&2
    exit 1
  fi
}

api_json() {
  local method="$1"
  local path="$2"
  local token="${3:-}"
  local data="${4:-}"
  local args=(--fail-with-body --silent --show-error --request "$method")
  if [[ -n "$token" ]]; then
    args+=(--header "Authorization: Bearer $token")
  fi
  if [[ -n "$data" ]]; then
    args+=(--header "Content-Type: application/json" --data "$data")
  fi
  curl "${args[@]}" "${BACKEND_URL%/}$path"
}

login_token() {
  local email="$1"
  local password="$2"
  local payload
  payload="$(jq -cn --arg email "$email" --arg password "$password" \
    '{email: $email, password: $password}')"
  api_json POST /auth/login "" "$payload" | jq -er '.access_token'
}

write_credentials() {
  local admin_token="$1"
  local driver_token="$2"
  local run_token="${3:-}"
  local temporary="$SMOKE_CREDENTIALS_FILE.tmp"
  {
    printf 'SMOKE_ADMIN_JWT=%q\n' "$admin_token"
    printf 'SMOKE_DRIVER_JWT=%q\n' "$driver_token"
    if [[ -n "$run_token" ]]; then
      printf 'SIMULATION_RUN_TOKEN=%q\n' "$run_token"
    fi
  } >"$temporary"
  chmod 600 "$temporary"
  mv "$temporary" "$SMOKE_CREDENTIALS_FILE"
}

load_credentials() {
  if [[ ! -f "$SMOKE_CREDENTIALS_FILE" ]]; then
    echo "Credentials file not found. Run ./smoke/prepare.sh first." >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$SMOKE_CREDENTIALS_FILE"
}

require_smoke_tools() {
  require_command curl
  require_command jq
  require_command uv
}
