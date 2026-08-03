#!/usr/bin/env bash

set -euo pipefail
# shellcheck source=lib.sh
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_smoke_tools
if [[ -e "$SMOKE_STATE_FILE" ]]; then
  echo "Refusing to overwrite existing smoke state: $SMOKE_STATE_FILE" >&2
  echo "Use a different SMOKE_RUNTIME_DIR for a fresh SimulationRun." >&2
  exit 1
fi

curl --fail --silent --show-error "${BACKEND_URL%/}/health" >/dev/null

admin_token="${SMOKE_ADMIN_JWT:-}"
if [[ -z "$admin_token" ]]; then
  require_value SMOKE_ADMIN_EMAIL
  require_value SMOKE_ADMIN_PASSWORD
  admin_token="$(login_token "$SMOKE_ADMIN_EMAIL" "$SMOKE_ADMIN_PASSWORD")"
fi
admin_me="$(api_json GET /auth/me "$admin_token")"
if ! jq -e '.roles | index("PlatformAdministrator") != null' <<<"$admin_me" >/dev/null; then
  echo "Configured administrator is not a PlatformAdministrator." >&2
  exit 1
fi

driver_id="${SMOKE_DRIVER_ID:-}"
if [[ -z "$driver_id" ]]; then
  require_value SMOKE_DRIVER_EMAIL
  users="$(api_json GET '/users?role=EVDriver&status=Active&account_type=Human' "$admin_token")"
  driver_id="$(jq -r --arg email "${SMOKE_DRIVER_EMAIL,,}" \
    '[.[] | select((.email | ascii_downcase) == $email)][0].id // empty' <<<"$users")"
  if [[ -z "$driver_id" ]]; then
    require_value SMOKE_DRIVER_PASSWORD
    require_value SMOKE_DRIVER_DISPLAY_NAME
    driver_payload="$(jq -cn \
      --arg email "$SMOKE_DRIVER_EMAIL" \
      --arg display_name "$SMOKE_DRIVER_DISPLAY_NAME" \
      --arg password "$SMOKE_DRIVER_PASSWORD" \
      '{email: $email, display_name: $display_name, password: $password,
        account_type: "Human", status: "Active", roles: ["EVDriver"], facility_ids: []}')"
    driver_id="$(api_json POST /users "$admin_token" "$driver_payload" | jq -er '.id')"
    echo "Created EVDriver $driver_id"
  else
    echo "Reusing EVDriver $driver_id"
  fi
else
  driver="$(api_json GET "/users/$driver_id" "$admin_token")"
  if ! jq -e '.status == "Active" and (.roles | index("EVDriver") != null)' \
    <<<"$driver" >/dev/null; then
    echo "SMOKE_DRIVER_ID must identify an active EVDriver." >&2
    exit 1
  fi
fi

driver_token="${SMOKE_DRIVER_JWT:-}"
if [[ -z "$driver_token" ]]; then
  require_value SMOKE_DRIVER_EMAIL
  require_value SMOKE_DRIVER_PASSWORD
  driver_token="$(login_token "$SMOKE_DRIVER_EMAIL" "$SMOKE_DRIVER_PASSWORD")"
fi
driver_me="$(api_json GET /auth/me "$driver_token")"
if [[ "$(jq -r '.id' <<<"$driver_me")" != "$driver_id" ]]; then
  echo "EVDriver JWT subject does not match $driver_id." >&2
  exit 1
fi

facility_id="${SMOKE_FACILITY_ID:-}"
facility_name="${SMOKE_FACILITY_NAME:-SPEC-013 Smoke Facility}"
if [[ -z "$facility_id" ]]; then
  facilities="$(api_json GET /facilities "$admin_token")"
  facility_id="$(jq -r --arg name "$facility_name" \
    '[.[] | select(.name == $name)][0].id // empty' <<<"$facilities")"
  if [[ -z "$facility_id" ]]; then
    facility_payload="$(jq -cn --arg name "$facility_name" \
      '{name: $name, facility_type: "University", timezone: "UTC", country: "Brazil",
        city: "Juiz de Fora", address: "Dedicated SPEC-013 synthetic smoke environment",
        operating_hours: null, status: "Active"}')"
    facility_id="$(api_json POST /facilities "$admin_token" "$facility_payload" | jq -er '.id')"
    echo "Created Facility $facility_id"
  else
    echo "Reusing Facility $facility_id"
  fi
fi
facility="$(api_json GET "/facilities/$facility_id" "$admin_token")"
if ! jq -e '.status == "Active" and .timezone == "UTC"' <<<"$facility" >/dev/null; then
  echo "Smoke Facility must be Active and use UTC." >&2
  exit 1
fi

station_id="${SMOKE_STATION_ID:-}"
station_serial="${SMOKE_STATION_SERIAL:-SCEP-SPEC013-SMOKE-1}"
if [[ -z "$station_id" ]]; then
  stations="$(api_json GET "/facilities/$facility_id/stations" "$admin_token")"
  station_id="$(jq -r --arg serial "$station_serial" \
    '[.[] | select(.serial_number == $serial)][0].id // empty' <<<"$stations")"
  if [[ -z "$station_id" ]]; then
    station_payload="$(jq -cn --arg serial "$station_serial" \
      '{name: "SPEC-013 Smoke Station", description: "Dedicated synthetic smoke station",
        serial_number: $serial, manufacturer: "SCEP", model: "Smoke-22",
        maximum_power_kw: 22, status: "Active",
        connectors: [{connector_type: "Type2", maximum_power_kw: 22, status: "Available"}]}')"
    station_id="$(api_json POST "/facilities/$facility_id/stations" \
      "$admin_token" "$station_payload" | jq -er '.id')"
    echo "Created Station $station_id"
  else
    echo "Reusing Station $station_id"
  fi
fi
station="$(api_json GET "/stations/$station_id" "$admin_token")"
if [[ "$(jq -r '.facility_id' <<<"$station")" != "$facility_id" ]] || \
  [[ "$(jq -r '.status' <<<"$station")" != "Active" ]]; then
  echo "Smoke Station must be Active and belong to the selected Facility." >&2
  exit 1
fi

connector_id="${SMOKE_CONNECTOR_ID:-}"
if [[ -z "$connector_id" ]]; then
  connector_id="$(jq -r '[.connectors[] | select(.status == "Available")][0].id // empty' \
    <<<"$station")"
fi
connector="$(jq -c --arg id "$connector_id" '.connectors[] | select(.id == $id)' \
  <<<"$station")"
if [[ -z "$connector" ]] || [[ "$(jq -r '.status' <<<"$connector")" != "Available" ]]; then
  echo "Smoke Connector must exist on the Station and be Available." >&2
  exit 1
fi
connector_type="$(jq -r '.connector_type' <<<"$connector")"
maximum_power_kw="$(jq -r '.maximum_power_kw' <<<"$connector")"

vehicle_id="${SMOKE_VEHICLE_ID:-}"
vehicle_name="${SMOKE_VEHICLE_NAME:-SPEC-013 Smoke Vehicle}"
if [[ -z "$vehicle_id" ]]; then
  vehicles="$(api_json GET /vehicles "$driver_token")"
  vehicle_id="$(jq -r --arg name "$vehicle_name" \
    '[.[] | select(.display_name == $name and .status == "ACTIVE")][0].id // empty' \
    <<<"$vehicles")"
  if [[ -z "$vehicle_id" ]]; then
    vehicle_payload="$(jq -cn --arg display_name "$vehicle_name" \
      '{display_name: $display_name}')"
    vehicle_id="$(api_json POST /vehicles "$driver_token" "$vehicle_payload" | jq -er '.id')"
    echo "Created Vehicle $vehicle_id"
  else
    echo "Reusing Vehicle $vehicle_id"
  fi
fi
vehicle="$(api_json GET "/vehicles/$vehicle_id" "$driver_token")"
if [[ "$(jq -r '.owner_id' <<<"$vehicle")" != "$driver_id" ]] || \
  [[ "$(jq -r '.status' <<<"$vehicle")" != "ACTIVE" ]]; then
  echo "Smoke Vehicle must be active and owned by the selected EVDriver." >&2
  exit 1
fi

logical_start_at="${SMOKE_LOGICAL_START_AT:-2026-01-05T00:00:00Z}"
logical_end_at="${SMOKE_LOGICAL_END_AT:-2026-01-06T00:00:00Z}"
session_hour="${SMOKE_SESSION_HOUR:-12}"
sessions_per_week="${SMOKE_SESSIONS_PER_WEEK:-1}"
scenario_sha256="$(
  cd "$ENGINE_DIR"
  uv run python -m smoke.generate_scenario \
    --output "$SMOKE_SCENARIO_FILE" \
    --logical-start-at "$logical_start_at" \
    --logical-end-at "$logical_end_at" \
    --session-hour "$session_hour" \
    --sessions-per-week "$sessions_per_week" \
    --driver-id "$driver_id" \
    --vehicle-id "$vehicle_id" \
    --facility-id "$facility_id" \
    --station-id "$station_id" \
    --connector-id "$connector_id" \
    --connector-type "$connector_type" \
    --maximum-power-kw "$maximum_power_kw"
)"

run_payload="$(jq -cn \
  --arg logical_start_at "$logical_start_at" \
  --arg logical_end_at "$logical_end_at" \
  --arg facility_id "$facility_id" \
  --arg driver_id "$driver_id" \
  --arg sha "$scenario_sha256" \
  '{logical_start_at: $logical_start_at, logical_end_at: $logical_end_at,
    facility_ids: [$facility_id], evdriver_ids: [$driver_id],
    external_scenario_id: "spec-013-operator-smoke", external_scenario_version: "1",
    scenario_sha256: $sha, simulator_version: "1.0.0"}')"
run="$(api_json POST /simulation-runs "$admin_token" "$run_payload")"
run_id="$(jq -er '.id' <<<"$run")"
api_json GET "/simulation-runs/$run_id/bootstrap" "$admin_token" \
  >"$SMOKE_DRAFT_BOOTSTRAP_FILE"
chmod 600 "$SMOKE_DRAFT_BOOTSTRAP_FILE"
if [[ "$(jq -r '.simulation_run.status' "$SMOKE_DRAFT_BOOTSTRAP_FILE")" != "DRAFT" ]]; then
  echo "Expected the prepared SimulationRun to remain DRAFT." >&2
  exit 1
fi

jq -n \
  --arg run_id "$run_id" \
  --arg facility_id "$facility_id" \
  --arg station_id "$station_id" \
  --arg connector_id "$connector_id" \
  --arg driver_id "$driver_id" \
  --arg vehicle_id "$vehicle_id" \
  --arg logical_start_at "$(jq -r '.logical_start_at' <<<"$run")" \
  --arg logical_end_at "$(jq -r '.logical_end_at' <<<"$run")" \
  --arg scenario_sha256 "$scenario_sha256" \
  '{simulation_run_id: $run_id, facility_id: $facility_id, station_id: $station_id,
    connector_id: $connector_id, driver_id: $driver_id, vehicle_id: $vehicle_id,
    logical_start_at: $logical_start_at, logical_end_at: $logical_end_at,
    scenario_sha256: $scenario_sha256}' >"$SMOKE_STATE_FILE"
chmod 600 "$SMOKE_STATE_FILE"
write_credentials "$admin_token" "$driver_token"

echo
echo "Prepared DRAFT SimulationRun $run_id"
echo "State:           $SMOKE_STATE_FILE"
echo "Scenario:        $SMOKE_SCENARIO_FILE"
echo "DRAFT bootstrap: $SMOKE_DRAFT_BOOTSTRAP_FILE"
echo "Credentials:     $SMOKE_CREDENTIALS_FILE (mode 600)"
echo "No SimulationRun token has been requested. Review the files, then run ./smoke/start.sh."
