#!/usr/bin/env bash

set -euo pipefail
# shellcheck source=lib.sh
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_smoke_tools
load_credentials
require_value SIMULATION_RUN_TOKEN
require_value SMOKE_DRIVER_JWT
for path in "$SMOKE_STATE_FILE" "$SMOKE_SCENARIO_FILE" "$SMOKE_BOOTSTRAP_FILE"; do
  if [[ ! -f "$path" ]]; then
    echo "Required smoke artifact not found: $path" >&2
    exit 1
  fi
done

driver_id="$(jq -er '.driver_id' "$SMOKE_STATE_FILE")"
export BACKEND_URL
export SIMULATION_SCENARIO_PATH="$SMOKE_SCENARIO_FILE"
export SIMULATION_BOOTSTRAP_PATH="$SMOKE_BOOTSTRAP_FILE"
export SIMULATION_CHECKPOINT_PATH="$SMOKE_CHECKPOINT_FILE"
export SIMULATION_REPORT_PATH="$SMOKE_REPORT_FILE"
export SIMULATION_RUN_TOKEN
export SIMULATION_DRIVER_TOKENS_JSON
SIMULATION_DRIVER_TOKENS_JSON="$(jq -cn \
  --arg driver_id "$driver_id" --arg token "$SMOKE_DRIVER_JWT" \
  '{($driver_id): $token}')"
export SIMULATION_REGISTERED_SCENARIO_SHA256
SIMULATION_REGISTERED_SCENARIO_SHA256="$(jq -er '.scenario_sha256' "$SMOKE_STATE_FILE")"

echo "Running the existing simulator entrypoint. Event logs remain visible below."
cd "$ENGINE_DIR"
uv run python -m app.main
