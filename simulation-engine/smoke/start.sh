#!/usr/bin/env bash

set -euo pipefail
# shellcheck source=lib.sh
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_smoke_tools
load_credentials
require_value SMOKE_ADMIN_JWT
if [[ ! -f "$SMOKE_STATE_FILE" ]]; then
  echo "State file not found. Run ./smoke/prepare.sh first." >&2
  exit 1
fi
run_id="$(jq -er '.simulation_run_id' "$SMOKE_STATE_FILE")"
run="$(api_json GET "/simulation-runs/$run_id" "$SMOKE_ADMIN_JWT")"
run_status="$(jq -r '.status' <<<"$run")"

if [[ "$run_status" == "DRAFT" ]]; then
  started="$(api_json POST "/simulation-runs/$run_id/start" "$SMOKE_ADMIN_JWT")"
  simulation_token="$(jq -er '.simulation_token' <<<"$started")"
  write_credentials "$SMOKE_ADMIN_JWT" "$SMOKE_DRIVER_JWT" "$simulation_token"
elif [[ "$run_status" == "RUNNING" && -n "${SIMULATION_RUN_TOKEN:-}" ]]; then
  echo "SimulationRun is already RUNNING; reusing the locally retained one-time token."
else
  echo "SimulationRun must be DRAFT, or RUNNING with its token already retained locally." >&2
  exit 1
fi

api_json GET "/simulation-runs/$run_id/bootstrap" "$SMOKE_ADMIN_JWT" \
  >"$SMOKE_BOOTSTRAP_FILE"
chmod 600 "$SMOKE_BOOTSTRAP_FILE"
if [[ "$(jq -r '.simulation_run.status' "$SMOKE_BOOTSTRAP_FILE")" != "RUNNING" ]]; then
  echo "RUNNING bootstrap export failed validation." >&2
  exit 1
fi

echo "Started SimulationRun $run_id"
echo "The one-time token is stored only in $SMOKE_CREDENTIALS_FILE (mode 600)."
echo "RUNNING bootstrap: $SMOKE_BOOTSTRAP_FILE"
echo "Execute the simulator with ./smoke/run.sh"
