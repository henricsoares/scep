# SCEP Digital Twin Simulation Engine

This directory contains the external SPEC-013 Version 1 simulator. It is an independent API client:
it does not import backend modules and never connects to PostgreSQL. The Backend API remains the
authority for identity, infrastructure, Reservations, Charging Sessions, Telemetry and Domain
Events.

With no scenario configured, the container checks backend health and exits successfully. A run is
executed only when the operator supplies the bootstrap, immutable scenario and credentials.

## Execution inputs

The administrator creates and starts a `SimulationRun`, saves the one-time run token securely and
exports `GET /simulation-runs/{id}/bootstrap`. Users, Vehicles and dedicated simulation
infrastructure must already exist.

Configure the process with:

```text
BACKEND_URL=http://localhost:8000
SIMULATION_SCENARIO_PATH=/work/scenario.json
SIMULATION_BOOTSTRAP_PATH=/work/bootstrap.json
SIMULATION_CHECKPOINT_PATH=/work/checkpoint.json
SIMULATION_REPORT_PATH=/work/report.json
SIMULATION_RUN_TOKEN=<one-time run token>
SIMULATION_DRIVER_TOKENS_JSON={"<evdriver UUID>":"<bearer JWT>"}
SIMULATION_REGISTERED_SCENARIO_SHA256=<optional registered digest>
```

Credential values must be injected by the deployment environment. They must not be committed to a
scenario, bootstrap, checkpoint or report. The optional registered digest is the `scenario_sha256`
configured on the run; when supplied, execution stops if the canonical scenario digest differs.

Run from this directory with:

```bash
uv run python -m app.main
```

## Scenario contract

Scenarios use versioned JSON. Weekdays use Python/ISO ordering (`0` Monday through `6` Sunday).
Weights are normalized by the planner and need not sum to one. The reference flow uses Reservation
probability `1.0` because SPEC-013 Version 1 Charging Sessions inherit provenance from a
Reservation.

```json
{
  "schema_version": "1.0",
  "scenario_id": "reference-week",
  "scenario_version": "1",
  "random_seed": 42,
  "logical_start_at": "2026-01-05T00:00:00Z",
  "logical_end_at": "2026-01-12T00:00:00Z",
  "telemetry_defaults": {
    "enabled": true,
    "sampling_interval_minutes": 15,
    "batch_size": 100,
    "bounded_power_noise": 0.05
  },
  "drivers": [
    {
      "driver_id": "00000000-0000-0000-0000-000000000001",
      "sessions_per_week": {"min": 2, "max": 5},
      "weekday_weights": {"0": 1, "1": 1, "2": 1, "3": 1, "4": 1},
      "hour_weights": {"9": 1, "18": 3},
      "facility_weights": {"00000000-0000-0000-0000-000000000002": 1},
      "reservation_probability": 1.0,
      "cancellation_probability": 0.05,
      "no_show_probability": 0.05,
      "lead_time_minutes": {"min": 30, "max": 120},
      "session_duration_minutes": {"min": 30, "max": 90},
      "power_utilization_factor": {"min": 0.5, "max": 0.9},
      "failure_handling": {
        "try_another_connector": true,
        "try_another_station": true,
        "try_another_facility": true,
        "maximum_alternative_attempts": 3,
        "rescheduling_delay_minutes": {"min": 15, "max": 60},
        "maximum_rescheduling_attempts": 2
      }
    }
  ]
}
```

The planner derives an independent stable random stream per EVDriver and stable event UUIDs. It
executes events in timestamp order, completes one global timestamp barrier before advancing,
reuses the same event ID for technical retries, and checkpoints resolved outcomes and completed
barriers. Restarting with the same run, scenario digest and simulator version replays uncertain
events safely through backend receipts.

Expected operational rejections can trigger the configured, bounded Connector, Station and
Facility alternatives after refreshing the driver's inventory. If alternatives are exhausted, the
simulator can shift the charging interval within the configured rescheduling limits. Every
alternative or rescheduled attempt receives a deterministic new event ID. Resolved domain
rejections remain resolved across checkpoint resume. Authentication, authorization, logical-time,
idempotency and simulation-contract failures terminate execution instead of activating the
behavioral fallback policy. Technical transport and server retries retain the original event ID and
use bounded exponential backoff with jitter.

The final report is an external artifact. The simulator does not complete or cancel the backend
run; an administrator performs that lifecycle transition after reviewing the report.

## Operator smoke validation

The reproducible one-Facility, one-EVDriver validation workflow is documented in
[`smoke/README.md`](smoke/README.md). It prepares a DRAFT run, retains credentials and generated
artifacts only in ignored local files, executes this existing entrypoint, verifies the resulting
resources through public APIs and leaves final run completion to the administrator.

The follow-up weekly validation in [`smoke/MULTI_DRIVER.md`](smoke/MULTI_DRIVER.md) provisions five
independent EVDriver profiles, multiple Stations and Connectors, then verifies week-long logical
time, deterministic stream ordering, Reservation-rooted Sessions, Telemetry and the final report.
