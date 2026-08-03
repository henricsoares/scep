#!/usr/bin/env bash

set -euo pipefail
# shellcheck source=lib.sh
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_smoke_tools
load_credentials
failures=0

pass() {
  echo "PASS $1"
}

fail() {
  echo "FAIL $1"
  failures=$((failures + 1))
}

skip() {
  echo "SKIP $1"
}

check_file() {
  local label="$1"
  local path="$2"
  if [[ -s "$path" ]]; then pass "$label"; else fail "$label"; fi
}

check_json() {
  local label="$1"
  local expression="$2"
  local path="$3"
  if jq -e "$expression" "$path" >/dev/null 2>&1; then pass "$label"; else fail "$label"; fi
}

for path in "$SMOKE_STATE_FILE" "$SMOKE_REPORT_FILE" "$SMOKE_CHECKPOINT_FILE"; do
  if [[ ! -f "$path" ]]; then
    fail "required artifact exists: $path"
  fi
done
if ((failures > 0)); then
  echo "OVERALL FAIL ($failures failed check(s))"
  exit 1
fi

run_id="$(jq -er '.simulation_run_id' "$SMOKE_STATE_FILE")"
driver_id="$(jq -er '.driver_id' "$SMOKE_STATE_FILE")"
vehicle_id="$(jq -er '.vehicle_id' "$SMOKE_STATE_FILE")"
connector_id="$(jq -er '.connector_id' "$SMOKE_STATE_FILE")"
logical_start_at="$(jq -er '.logical_start_at' "$SMOKE_STATE_FILE")"
logical_end_at="$(jq -er '.logical_end_at' "$SMOKE_STATE_FILE")"

check_file "checkpoint file exists and is non-empty" "$SMOKE_CHECKPOINT_FILE"
check_file "report file exists and is non-empty" "$SMOKE_REPORT_FILE"
check_json "checkpoint contains successful event IDs" \
  '.completed_event_ids | length > 0' "$SMOKE_CHECKPOINT_FILE"
check_json "report state is FINISHED" '.state == "FINISHED"' "$SMOKE_REPORT_FILE"
check_json "successful_event_count is positive" '.successful_event_count > 0' "$SMOKE_REPORT_FILE"
check_json "at least one Reservation was created" '.reservations_created >= 1' "$SMOKE_REPORT_FILE"
check_json "at least one Charging Session was activated" \
  '.charging_sessions_activated >= 1' "$SMOKE_REPORT_FILE"
check_json "at least one Charging Session was completed" \
  '.charging_sessions_completed >= 1' "$SMOKE_REPORT_FILE"
check_json "Telemetry samples were submitted" \
  '.telemetry_samples_submitted > 0' "$SMOKE_REPORT_FILE"
check_json "no terminal simulator failure occurred" \
  '.terminal_failure_count == 0' "$SMOKE_REPORT_FILE"
check_json "no unresolved simulator warning occurred" \
  '.unresolved_warnings | length == 0' "$SMOKE_REPORT_FILE"

if run="$(api_json GET "/simulation-runs/$run_id" "$SMOKE_ADMIN_JWT")"; then
  if [[ "$(jq -r '.status' <<<"$run")" == "RUNNING" ]]; then
    pass "SimulationRun remains RUNNING before administrator completion"
  else
    fail "SimulationRun remains RUNNING before administrator completion"
  fi
  if [[ "$(jq -r '.last_accepted_simulated_at // empty' <<<"$run")" != "" ]]; then
    pass "last_accepted_simulated_at advanced"
  else
    fail "last_accepted_simulated_at advanced"
  fi
else
  fail "SimulationRun is retrievable through the administrative API"
fi

reservations="$(api_json GET "/connectors/$connector_id/reservations?limit=200" \
  "$SMOKE_ADMIN_JWT")"
matching_reservations="$(jq -c \
  --arg driver_id "$driver_id" \
  --arg vehicle_id "$vehicle_id" \
  --arg start "$logical_start_at" \
  --arg end "$logical_end_at" \
  '[.[] | select(.owner_id == $driver_id and .vehicle_id == $vehicle_id and
    .start_at >= $start and .end_at <= $end)]' <<<"$reservations")"
if [[ "$(jq 'length' <<<"$matching_reservations")" -ge 1 ]]; then
  pass "at least one simulated-window Reservation is visible through the public API"
else
  fail "at least one simulated-window Reservation is visible through the public API"
fi

reservation_ids="$(jq '[.[].id]' <<<"$matching_reservations")"
sessions="$(api_json GET "/charging-sessions?connector_id=$connector_id&limit=200" \
  "$SMOKE_ADMIN_JWT")"
matching_sessions="$(jq -c --argjson reservation_ids "$reservation_ids" \
  '[.[] | select(.status == "COMPLETED" and (.reservation_id as $id |
    $reservation_ids | index($id) != null))]' <<<"$sessions")"
if [[ "$(jq 'length' <<<"$matching_sessions")" -ge 1 ]]; then
  pass "at least one completed Charging Session is visible through the public API"
else
  fail "at least one completed Charging Session is visible through the public API"
fi

session_id="$(jq -r '.[0].id // empty' <<<"$matching_sessions")"
if [[ -n "$session_id" ]]; then
  telemetry="$(api_json GET "/charging-sessions/$session_id/telemetry?limit=200" \
    "$SMOKE_ADMIN_JWT")"
  if [[ "$(jq 'length' <<<"$telemetry")" -gt 0 ]]; then
    pass "Telemetry is visible for the completed simulated Session"
  else
    fail "Telemetry is visible for the completed simulated Session"
  fi
else
  fail "Telemetry is queryable for a completed simulated Session"
fi

skip "Reservation simulation_run_id provenance is persisted but not exposed by ReservationResponse"
skip "ChargingSession simulation_run_id provenance is persisted but not exposed by ChargingSessionResponse"
skip "Telemetry provenance is derived through the Session and is not a Telemetry response field"

if ((failures == 0)); then
  echo "OVERALL PASS"
  exit 0
fi
echo "OVERALL FAIL ($failures failed check(s))"
exit 1
