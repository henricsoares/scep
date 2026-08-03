#!/usr/bin/env bash

set -euo pipefail
# shellcheck source=lib.sh
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_smoke_tools
load_credentials
if [[ ! -f "$SMOKE_REPORT_FILE" ]] || \
  [[ "$(jq -r '.state // empty' "$SMOKE_REPORT_FILE")" != "FINISHED" ]]; then
  echo "A FINISHED local report is required before administrator completion." >&2
  exit 1
fi
run_id="$(jq -er '.simulation_run_id' "$SMOKE_STATE_FILE")"
completed="$(api_json POST "/simulation-runs/$run_id/complete" "$SMOKE_ADMIN_JWT")"
if [[ "$(jq -r '.status' <<<"$completed")" != "COMPLETED" ]]; then
  echo "SimulationRun completion did not return COMPLETED." >&2
  exit 1
fi
echo "PASS SimulationRun $run_id completed by the Platform Administrator"
