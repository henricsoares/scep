# SPEC-013 operator smoke validation

This workflow creates or reuses one dedicated Facility, Station, Connector, EVDriver and Vehicle,
then prepares a one-day `SimulationRun` that deterministically exercises:

```text
Reservation -> Session activation -> Telemetry batch -> Session completion
```

It uses only public SCEP APIs and the existing simulator entrypoint. It does not clean up resources,
change production behavior or complete the backend run automatically.

## Prerequisites

- Bash, `curl`, `jq` and `uv`;
- Docker with Compose;
- a local Platform Administrator account;
- the PR #53 implementation checked out.

From the repository root, start SCEP and wait for health:

```bash
docker compose up --build -d
curl --fail http://localhost:8000/health
```

The Compose simulator container only checks backend health when no scenario is configured. The
operator workflow below runs the simulator from `simulation-engine/` with explicit local inputs.

## 1. Configure local credentials and optional resource IDs

```bash
cd simulation-engine
cp smoke/.env.example smoke/.env
chmod 600 smoke/.env
```

Edit `smoke/.env`. Supply either `SMOKE_ADMIN_JWT` or administrator login credentials. Supply an
EVDriver email and password so the helper can create or log in through `POST /users` and
`POST /auth/login`; alternatively supply both `SMOKE_DRIVER_ID` and `SMOKE_DRIVER_JWT`.

The password and token values are local secrets. `smoke/.env`, `smoke/runtime/`, generated
bootstraps, scenario, checkpoint, report and the plaintext run token are ignored by Git.

Existing Facility, Station, Connector, EVDriver and Vehicle IDs may be supplied. Otherwise the
helper discovers resources by the stable smoke names and creates missing ones through their normal
APIs. It never deletes or mutates unrelated resources. The selected Facility must be dedicated,
Active and use UTC; the Station and Connector must also be operational.

## 2. Prepare resources and a DRAFT run

```bash
./smoke/prepare.sh
```

The helper:

1. authenticates the Platform Administrator;
2. creates or reuses the dedicated infrastructure and EVDriver;
3. creates or reuses one active Vehicle owned by that EVDriver;
4. generates and validates the Pydantic scenario;
5. registers its canonical SHA-256 while creating a DRAFT `SimulationRun`;
6. exports the DRAFT bootstrap;
7. writes the resulting IDs to `smoke/runtime/state.json`.

Inspect the generated contract before starting:

```bash
jq . smoke/runtime/state.json
jq . smoke/runtime/scenario.json
jq . smoke/runtime/bootstrap-draft.json
```

The default window is Monday `2026-01-05T00:00:00Z` through Tuesday midnight. Exactly one attempt
is planned for Monday 12:00 UTC, with a 60-minute lead time, 60-minute Session, fixed 50% Connector
power, 15-minute Telemetry sampling, Reservation probability `1.0`, and cancellation/no-show
probabilities `0`. Conservative failure handling disables alternatives and rescheduling so any
unexpected operational conflict is visible in verification.

## 3. Explicitly start the run

```bash
./smoke/start.sh
```

This is the only step that calls `POST /simulation-runs/{id}/start`. It captures the one-time token
in `smoke/runtime/credentials.env` with mode `600` and re-exports a RUNNING bootstrap to
`smoke/runtime/bootstrap.json`. Neither token is printed.

## 4. Execute the existing simulator

```bash
./smoke/run.sh
```

The script exports the existing `BACKEND_URL`, `SIMULATION_SCENARIO_PATH`,
`SIMULATION_BOOTSTRAP_PATH`, `SIMULATION_CHECKPOINT_PATH`, `SIMULATION_REPORT_PATH`,
`SIMULATION_RUN_TOKEN`, `SIMULATION_DRIVER_TOKENS_JSON` and
`SIMULATION_REGISTERED_SCENARIO_SHA256` settings, then runs exactly:

```bash
uv run python -m app.main
```

Simulator stdout remains attached. Each JSON log line identifies the operation, event ID, logical
time and outcome without exposing credentials. After completion inspect:

```bash
jq . smoke/runtime/checkpoint.json
jq . smoke/runtime/report.json
```

The local report should be `FINISHED`; the backend run intentionally remains `RUNNING`.

## 5. Verify through public APIs

```bash
./smoke/verify.sh
```

The verifier prints only `PASS`, `FAIL` and `SKIP` checks, followed by `OVERALL PASS` or
`OVERALL FAIL`. It checks run state and clock advancement, report counters, visible Reservations,
completed Charging Sessions and Telemetry. Current public Reservation and Charging Session response
schemas do not expose `simulation_run_id`, so provenance checks are reported as `SKIP`; no test-only
production endpoint is added. Persistence-level provenance remains covered by the automated
integration tests in PR #53.

## 6. Complete the run as administrator

Only after `OVERALL PASS`:

```bash
./smoke/complete.sh
```

This calls the normal administrator completion endpoint. The simulator never performs this
lifecycle transition.

## Optional checkpoint/restart validation

Use a fresh runtime directory so the original evidence remains untouched:

```bash
export SMOKE_RUNTIME_DIR="$PWD/smoke/runtime-restart"
./smoke/prepare.sh
./smoke/start.sh
./smoke/run.sh
```

Interrupt `run.sh` with `Ctrl+C` after event logs begin, preserving the generated checkpoint. Run
the exact same `./smoke/run.sh` command again. The simulator reloads the same scenario, bootstrap,
token and checkpoint; completed event IDs remain resolved and uncertain events reuse their stable
IDs, allowing backend receipts to prevent duplicate business mutations. Then run `verify.sh` and
`complete.sh` with the same `SMOKE_RUNTIME_DIR` exported.

The primary four-event scenario can finish quickly. For a larger interruption window, set a fresh
seven-day logical window and increase `SMOKE_SESSIONS_PER_WEEK` before `prepare.sh`. This optional
exercise may encounter ordinary capacity conflicts on one Connector; it validates checkpoint safety,
not a second happy-path guarantee. Never reuse a completed run or mix artifacts from different
runtime directories.
