# SCEP Backend

FastAPI modular monolith for SCEP.

## Reservations

SPEC-006 is implemented inside the existing Smart Charging module. Authenticated Human and
Technical Client identities can manage owned Vehicles and Reservations. Platform Administrators
can manage all owned resources, while operational and research roles retain the read-only scopes
defined by SPEC-005 and SPEC-006.

Vehicle routes:

```text
POST  /vehicles
GET   /vehicles
GET   /vehicles/{vehicleId}
PATCH /vehicles/{vehicleId}
```

Reservation routes:

```text
POST  /reservations
GET   /reservations
GET   /reservations/{reservationId}
PATCH /reservations/{reservationId}
POST  /reservations/{reservationId}/cancel
GET   /connectors/{connectorId}/reservations
```

Reservation timestamps require an explicit ISO 8601 offset and are normalized to UTC. Intervals
are half-open (`[start_at, end_at)`). PostgreSQL partial GiST exclusion constraints protect both
Connector and Vehicle calendars against concurrent overlap in the `CONFIRMED` and `ACTIVE`
statuses.

No-Show processing uses deterministic opportunistic reconciliation. Every Reservation read or
write first marks overdue `CONFIRMED` rows as `NO_SHOW` when the current application-clock instant
is later than `start_at + 15 minutes`. This releases both calendars before externally observable
Reservation behavior without requiring a separate scheduler or manual action. The reconciliation
operation is idempotent because it selects only `CONFIRMED` rows.

## Charging Sessions

SPEC-007 executes eligible Reservations through historical Charging Sessions:

```text
POST /reservations/{reservationId}/charging-session
GET  /charging-sessions
GET  /charging-sessions/{sessionId}
POST /charging-sessions/{sessionId}/complete
GET  /connectors/{connectorId}/charging-sessions
GET  /vehicles/{vehicleId}/charging-sessions
```

Activation and completion each use one database transaction. PostgreSQL advisory transaction
locks serialize Reservation, Vehicle and Connector keys, while unique indexes provide final
database guards. On completion, the Connector becomes `OutOfService` when its Station or Facility
is inactive, `Reserved` when another currently effective confirmed Reservation exists, and
otherwise `Available`.

Prometheus exposes activation, completion, failure and conflict counters under the
`scep_charging_session*` namespace. Direct sessions, telemetry, OCPP, energy calculation, billing,
notifications and Domain Events remain outside SPEC-007.

## Current Backend Capabilities

Subsequent approved specifications extend the same modular monolith with:

- immutable single and batch Telemetry ingestion from normal and simulated Sessions;
- transactional Domain Event persistence and post-commit internal dispatch;
- authenticated read-only Analytics overview and time-series endpoints;
- CSV and Parquet Dataset Exports with processing-time snapshots, integrity and provenance;
- the SPEC-013 `SimulationRun` lifecycle, run-scoped credential validation, immutable event
  receipts, logical-clock enforcement and Reservation-to-Session simulation provenance.

The behavioral Digital Twin engine remains in `simulation-engine/`. The backend does not plan
scenarios or generate synthetic behavior; it validates the restricted simulation context and
applies existing domain rules atomically. Normal requests do not require simulation headers.
