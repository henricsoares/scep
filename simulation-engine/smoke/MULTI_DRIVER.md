# SPEC-013 Multi-Driver Weekly Smoke

This smoke validation exercises five independent deterministic EVDriver streams over one logical
week. It complements the single-driver operator smoke; it is not a load test.

## Scenario

| Driver | Profile | Attempts per week | Weighted local UTC hours |
| --- | --- | ---: | --- |
| 1 | Morning commuter | 5 | 08:00-10:59, strongly weighted to 08:00-09:59 |
| 2 | Evening commuter | 4 | 17:00-20:59, strongly weighted to 18:00-19:59 |
| 3 | Moderate use | 3 | 07:00, 12:00, 16:00 and 21:00 |
| 4 | Weekend occasional | 2 | Saturday and Sunday only |
| 5 | High utilization | 5 | 06:00 through 21:59 with varied weights |

Every profile uses:

- `reservation_probability = 1.0`;
- `cancellation_probability = 0.10`;
- `no_show_probability = 0.10`;
- 30-120 minute lead and Session-duration ranges;
- 15-minute Telemetry with bounded power noise;
- weighted-random Connector selection;
- at most two Connector/Station alternatives and two bounded rescheduling attempts.

The isolated inventory contains one UTC Facility, two Stations and three Type2 Connectors. The
second Station makes Station fallback testable without introducing a second timezone or Facility.

## Prepare with Insomnia

Import `../../docs/api/scep-spec013-multi-driver-insomnia.json` into a fresh workspace. Before
starting, set the four lowercase `simulator_*_path` variables to absolute paths under:

```text
simulation-engine/smoke/runtime-insomnia-multi/
```

Run requests 01 through 24 in order. Request 22 starts the run and captures the one-time credential.
Request 23 is the only response that shall be saved as `bootstrap.json`.

To avoid escaped JSON when copying values from Insomnia, copy the complete Base Environment JSON
into the ignored local file:

```text
simulation-engine/smoke/runtime-insomnia-multi/environment.json
```

Then materialize the simulator inputs from `simulation-engine/`:

```bash
mkdir -p smoke/runtime-insomnia-multi
chmod 700 smoke/runtime-insomnia-multi
chmod 600 smoke/runtime-insomnia-multi/environment.json
jq -r '.scenario_json' smoke/runtime-insomnia-multi/environment.json \
  > smoke/runtime-insomnia-multi/scenario.json
jq -r '.simulator_env' smoke/runtime-insomnia-multi/environment.json > .env
chmod 600 .env smoke/runtime-insomnia-multi/scenario.json \
  smoke/runtime-insomnia-multi/bootstrap.json
```

Do not set `SIMULATION_REGISTERED_SCENARIO_SHA256`: the Insomnia run intentionally registers no
digest. Validate both generated inputs before execution:

```bash
uv run python -c \
  "from pathlib import Path; from app.scenarios.schema import Scenario, Bootstrap; Scenario.model_validate_json(Path('smoke/runtime-insomnia-multi/scenario.json').read_text()); Bootstrap.model_validate_json(Path('smoke/runtime-insomnia-multi/bootstrap.json').read_text()); print('inputs valid')"
```

## Execute and inspect

Run from `simulation-engine/`, leaving stdout attached and preserving an operator log:

```bash
uv run python -m app.main 2>&1 | tee smoke/runtime-insomnia-multi/simulator.log
```

The process shall exit successfully. Check the minimum report contract:

```bash
jq -e '
  .state == "FINISHED" and
  .terminal_failure_count == 0 and
  .unresolved_warnings == [] and
  .planned_event_count >= (.successful_event_count + .domain_rejected_event_count) and
  .reservations_created > 0 and
  .charging_sessions_activated > 0 and
  .charging_sessions_completed > 0 and
  .telemetry_samples_submitted > 0 and
  (.last_processed_logical_timestamp >= "2026-01-10T00:00:00Z")
' smoke/runtime-insomnia-multi/report.json
```

With fallback or rescheduling enabled, strict equality between planned and successful plus rejected
events is not a stable invariant. The plan count includes original and generated events, while
dependent events may be resolved without execution after an expected rejection.

Confirm five independent driver streams and global non-decreasing logical ordering from the log:

```bash
rg '^\{"event": "simulation_event"' smoke/runtime-insomnia-multi/simulator.log \
  | jq -s -e '([.[].driver_id] | unique | length) == 5'
rg '^\{"event": "simulation_event"' smoke/runtime-insomnia-multi/simulator.log \
  | jq -s -e '([.[].logical_time] == ([.[].logical_time] | sort))'
```

Confirm that checkpoint outcome identifiers do not overlap:

```bash
jq -e '
  ((.completed_event_ids + .rejected_event_ids) | length) ==
  ((.completed_event_ids + .rejected_event_ids) | unique | length)
' smoke/runtime-insomnia-multi/checkpoint.json
```

Expected domain rejection, fallback, cancellation or no-show counts may be zero for a particular
deterministic set of generated UUIDs. This smoke validates correct handling when they occur; it does
not require forcing every probabilistic branch in one run.

## Verify through the API and complete

After the report is `FINISHED`, run Insomnia requests 25 through 30. They verify clock advancement,
collect Reservations across all three Connectors, require accepted Reservation activity from all
five drivers, require every returned Session to reference one of those Reservations and inspect
simulator Telemetry. A driver whose accepted Reservation becomes `NO_SHOW` legitimately has no
Charging Session, so the smoke does not require completed Sessions from all five drivers.

Run request 31 only after the report and API checks pass. It completes the backend `SimulationRun`
as Platform Administrator. Current public resources do not expose `simulation_run_id`; exact
persistence-level provenance remains covered by the automated integration tests.
