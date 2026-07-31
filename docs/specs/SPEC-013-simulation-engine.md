# SPEC-013 — Digital Twin Simulation Engine

## Smart Charging Experimentation Platform (SCEP)

**Document Status:** Draft / Under Review

**Implementation Status:** Planned

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

**Depends on:**

- SPEC-002 — Domain Model and Ubiquitous Language
- SPEC-003 — Facilities
- SPEC-004 — Charging Stations
- SPEC-005 — Identity and Access
- SPEC-006 — Reservations
- SPEC-007 — Charging Sessions
- SPEC-008 — Telemetry
- ADR-005 — Adopt an External Digital Twin Simulation Engine

**Related specifications:**

- SPEC-010 — Analytics
- SPEC-011 — Dataset Export
- SPEC-012 — Weekly Occupancy Predictions

**Related planning:**

- GitHub issue #46 — research Roles and non-human actor authorization

---

# 1. Purpose

This specification defines the Version 1 contract for a Digital Twin Simulation Engine that
produces reproducible synthetic Smart Charging activity through the public SCEP APIs.

The Simulation Engine is an independent external application. It shall behave as a controlled API
client, authenticate as configured EVDrivers, create Reservations, activate and complete Charging
Sessions, and optionally submit Telemetry. It shall not access PostgreSQL, invoke internal backend
modules or implement SCEP business rules.

The Backend API remains the authority for authentication, authorization, domain validation,
persistence, Domain Events and operational consistency. Version 1 adds only the simulation context
required to execute accelerated historical scenarios safely, idempotently and with traceable
provenance.

Analytics, Dataset Export and Predictions may later consume the persisted synthetic activity, but
none of them is a runtime prerequisite for simulation execution.

---

# 2. Goals

Version 1 shall:

- keep the Simulation Engine outside the Backend API and Modular Monolith;
- generate operationally valid synthetic data only through public REST APIs;
- support accelerated logical time without duplicating domain rules;
- preserve chronological and causal behavior for each EVDriver;
- provide deterministic scenario generation from a stable seed and configuration;
- authorize each execution through a controlled `SimulationRun`;
- restrict each run to explicit Facilities and EVDrivers;
- preserve simulation provenance in Reservations and Charging Sessions;
- make successful mutable operations safe to retry through event-level idempotency;
- support existing atomic Telemetry batch ingestion;
- reuse the existing `Clock` abstraction and domain services;
- prevent simulated no-show reconciliation from affecting real data or another run;
- provide a minimal versioned bootstrap for the external simulator;
- expose sufficient logs, receipts and lifecycle metadata for diagnosis and audit;
- preserve normal non-simulated behavior when no simulation context is supplied.

---

# 3. Scope

This specification includes:

- the external Simulation Engine responsibility boundary;
- the `SimulationRun` aggregate and lifecycle;
- explicit Facility and EVDriver authorization per run;
- run-scoped execution credentials;
- simulation request headers and request-scoped context;
- logical-time validation and monotonic advancement;
- successful-event idempotency receipts;
- simulation provenance on Reservation and Charging Session;
- partitioned no-show reconciliation;
- the Version 1 allowlist of simulated operations;
- minimal bootstrap export;
- deterministic scenario configuration and per-EVDriver behavior;
- chronological event planning, retries, conflict handling and checkpointing;
- Telemetry batch usage;
- completion validation;
- persistence, migrations, observability, security and testing expectations.

## 3.1 Out of Scope

Version 1 shall not include:

- an internal backend simulation module;
- direct database access by the Simulation Engine;
- simulation logic inside domain entities or services;
- AI model execution, reinforcement learning or adaptive learned behavior;
- OCPP device simulation;
- electrical-grid simulation;
- detailed battery degradation or electrochemical models;
- route, traffic, weather, tariff or geospatial optimization;
- simulated creation of Users, Vehicles, Facilities, Stations or Connectors;
- simulated infrastructure maintenance or equipment-failure mutations;
- delegated OAuth tokens, token exchange or impersonation;
- a permanent non-human client identity model;
- idempotency receipts for rejected domain operations;
- backend ordering of simultaneous conflicting events;
- concurrent execution across distinct logical timestamps;
- synthetic-data isolation across every operational query;
- Dataset Export filtering by `simulation_run_id`;
- Analytics separation between real and simulated activity;
- automatic retention, cleanup or deletion of completed runs;
- automatic completion of a run by the external simulator;
- knowledge of the simulator's complete external event plan in the Backend API;
- unrelated frontend implementation.

The omitted data-isolation capabilities are future improvements. Version 1 guarantees provenance,
not automatic exclusion of synthetic activity from every existing read model.

---

# 4. Architectural Context

The Version 1 flow is:

```text
Administrator
  creates resources and SimulationRun
              │
              ▼
     Bootstrap Export API
              │
              ▼
External Simulation Engine
  scenario planning and logical clock
              │
              ▼
Public SCEP REST APIs
  authenticated EVDriver requests
  + validated simulation context
              │
              ▼
Existing Domain Services
  Reservation, Session, Telemetry
              │
              ▼
PostgreSQL and Domain Events
```

The Simulation Engine shall live as an independently executable application. It may reside in the
same source repository for delivery convenience, but it shall have its own entry point,
configuration, dependency boundary, container image and lifecycle.

The Backend API shall know that an accepted request belongs to a `SimulationRun` because Version 1
requires logical time, provenance and idempotency. This knowledge does not permit simulation logic
to enter the domain. The simulator still behaves externally and the domain still applies the same
business invariants.

---

# 5. Ubiquitous Language

## 5.1 Digital Twin Simulation Engine

The independent external application that generates realistic synthetic Smart Charging behavior
and sends it through public SCEP APIs.

## 5.2 SimulationRun

The backend-owned authorization, logical-time and provenance context for exactly one controlled
simulation execution. It does not contain or execute the behavioral scenario.

## 5.3 Logical Time

The scenario time supplied by the Simulation Engine as `X-Simulated-At` and validated by the
Backend API. Domain services observe this value through a request-scoped `Clock`.

## 5.4 Real Processing Time

The actual UTC time at which the Backend API receives, persists and completes a request. It remains
available for audit, logs and receipt timestamps.

## 5.5 Simulation Event

One logical mutable action generated by the Simulation Engine, identified by a stable
`X-Simulation-Event-Id`.

## 5.6 Simulation Event Receipt

An immutable backend record proving that one successful Simulation Event was accepted and applied.
It provides event-level idempotency and traceability.

## 5.7 Bootstrap

A minimal, versioned document exported by SCEP for one `SimulationRun`. It contains the run window
and authorized resource identifiers, but no credentials or behavioral configuration.

## 5.8 Scenario Configuration

The external immutable configuration that defines deterministic simulated behavior. It belongs to
the Simulation Engine, not the Backend API.

---

# 6. Responsibility Boundaries

## 6.1 Backend API

The Backend API shall own:

- `SimulationRun` lifecycle and persistence;
- authorized Facility and EVDriver associations;
- generation and verification of the run-scoped execution credential;
- request-context validation;
- logical-time window and monotonicity enforcement;
- Facility-scope authorization for each mutation;
- existing Reservation, Charging Session and Telemetry domain rules;
- partitioned no-show reconciliation;
- successful-event idempotency receipts;
- provenance persistence;
- bootstrap export;
- completion validation;
- real processing timestamps and audit metadata.

## 6.2 Simulation Engine

The Simulation Engine shall own:

- external scenario files and schemas;
- random seed and deterministic planning;
- per-EVDriver behavioral configuration;
- authentication as each configured EVDriver;
- secure retrieval of the run-scoped execution credential;
- logical-clock progression;
- event ordering and causal sequencing;
- alternative-resource selection;
- retry, rescheduling and abandonment policy;
- local checkpoints and resume behavior;
- structured logs and final execution report;
- optional Telemetry generation.

## 6.3 Domain Ownership

The Simulation Engine shall not decide whether an operation is valid. It may request an action, but
SCEP shall continue to validate all domain invariants.

A request accepted under simulation context shall not bypass:

- Reservation interval and duration rules;
- Facility operating hours;
- Connector and Station state;
- Vehicle ownership;
- overlap and conflict rules;
- Charging Session activation windows;
- session-completion rules;
- Telemetry consistency rules;
- authorization boundaries.

---

# 7. SimulationRun Aggregate

A `SimulationRun` shall contain at least:

- `id` — immutable UUID;
- `status` — `DRAFT`, `RUNNING`, `COMPLETED` or `CANCELLED`;
- `logical_start_at` — inclusive UTC instant;
- `logical_end_at` — inclusive UTC instant;
- `last_accepted_simulated_at` — nullable UTC instant;
- `credential_hash` — hash of the run-scoped execution credential;
- optional `external_scenario_id`;
- optional `external_scenario_version`;
- optional `scenario_sha256`;
- optional `simulator_version`;
- `created_by` — authenticated administrative subject;
- `created_at` and `updated_at` — real processing timestamps;
- optional `started_at`, `completed_at` and `cancelled_at` — real processing timestamps.

The run shall have explicit many-to-many associations with:

- one or more Facilities;
- one or more EVDriver Users.

Stations and Connectors are not associated directly. They are authorized dynamically through their
current Facility hierarchy.

## 7.1 Lifecycle

Allowed transitions are:

```text
DRAFT -> RUNNING
DRAFT -> CANCELLED
RUNNING -> COMPLETED
RUNNING -> CANCELLED
```

All other transitions shall be rejected.

A run shall not be reopened. `COMPLETED` and `CANCELLED` are terminal.

## 7.2 DRAFT

While `DRAFT`, an authorized administrator may change:

- the logical window;
- authorized Facilities;
- authorized EVDrivers;
- external scenario references.

No simulated operation shall be accepted.

## 7.3 Start

Starting a run shall:

- require `DRAFT` status;
- validate `logical_start_at < logical_end_at`;
- require at least one Facility and one EVDriver;
- verify all associated resources exist;
- verify associated Users have the EVDriver Role and are active;
- generate or rotate the run-scoped execution credential;
- store only its secure hash;
- set status to `RUNNING`;
- set `started_at` using real processing time;
- leave `last_accepted_simulated_at` as `null`.

The plaintext execution credential shall be returned only through a deliberate secure administrative
operation and shall not be included in the bootstrap, logs or ordinary run reads.

## 7.4 Complete

Completion shall:

- require `RUNNING` status;
- lock the run against concurrent simulated mutations;
- perform final no-show reconciliation for the run at `logical_end_at`;
- reject completion while any associated Charging Session remains `ACTIVE`;
- set status to `COMPLETED`;
- set `completed_at` using real processing time.

Version 1 does not require the backend to know whether every externally planned event was sent.
Confirmed Reservations remaining after final reconciliation do not block completion unless the
existing domain rules leave them eligible for a required transition.

## 7.5 Cancel

Cancellation shall be permitted from `DRAFT` or `RUNNING`.

Cancellation shall:

- prevent all later simulated mutations;
- preserve all previously persisted operational data and receipts;
- set `cancelled_at` using real processing time;
- invalidate the execution credential for further use.

Cancellation shall not automatically delete, compensate or rewrite prior activity.

---

# 8. Administrative APIs

Version 1 shall expose authenticated administrative contracts equivalent to:

```text
POST   /simulation-runs
GET    /simulation-runs/{simulationRunId}
PATCH  /simulation-runs/{simulationRunId}
POST   /simulation-runs/{simulationRunId}/start
POST   /simulation-runs/{simulationRunId}/complete
POST   /simulation-runs/{simulationRunId}/cancel
GET    /simulation-runs/{simulationRunId}/bootstrap
```

Final route naming shall follow repository conventions.

`PATCH` shall be accepted only for `DRAFT` runs.

The lifecycle APIs shall use optimistic request validation plus transactional locking to prevent
invalid concurrent transitions.

The final authorization mapping shall follow SPEC-005. Version 1 conceptually requires an
administrative subject such as `PlatformAdministrator`; a future Researcher Role may be added by a
separate identity decision.

---

# 9. Bootstrap Contract

The bootstrap shall be minimal, versioned and specific to one run.

Example:

```json
{
  "bootstrap_version": "1.0",
  "api_version": "1",
  "generated_at": "2026-07-31T15:00:00Z",
  "simulation_run": {
    "id": "c5fbdbcf-6a42-4a9d-907d-b94117f0b3e7",
    "status": "RUNNING",
    "logical_start_at": "2026-01-01T00:00:00Z",
    "logical_end_at": "2026-03-31T23:59:59Z"
  },
  "authorized_facility_ids": [
    "80fdd728-1cda-487f-aad1-965c5ca070e2"
  ],
  "authorized_evdriver_ids": [
    "bb21f326-d194-427d-a9f9-70fb46098a25"
  ]
}
```

The bootstrap shall not contain:

- passwords;
- access or refresh tokens;
- the run-scoped execution credential;
- credential references;
- Stations or Connectors;
- current operational status snapshots;
- Vehicles;
- scenario behavior;
- random seed;
- probabilities or timing distributions;
- historical operational data;
- an absolute API base URL that may be incorrect behind a proxy.

The simulator shall obtain API location from deployment configuration. It shall query current
Facilities, Stations, Connectors and Vehicles through existing read APIs before execution and may
refresh a local cache during execution.

Bootstrap export may be available for audit in any status, but the simulator shall start or resume
only when the run is `RUNNING`.

---

# 10. Authentication and Request Context

Every simulated mutable request shall carry two independent authorities:

1. the normal EVDriver bearer JWT;
2. a run-scoped high-entropy execution credential.

The EVDriver JWT establishes who performs the domain action. The run credential proves that the
request belongs to the authorized simulation execution.

Version 1 shall use headers equivalent to:

```http
Authorization: Bearer <evdriver-token>
X-Simulation-Token: <run-scoped-secret>
X-Simulation-Run-Id: <uuid>
X-Simulated-At: <RFC3339 timestamp with explicit offset>
X-Simulation-Event-Id: <uuid>
```

The exact canonical header names shall be documented in OpenAPI.

A free client-declared identity such as `X-Client-Id` shall not authenticate the simulator.

The run credential shall:

- be generated with sufficient entropy;
- be stored only as a secure hash;
- use constant-time verification;
- be specific to one run;
- be invalid outside `RUNNING` status;
- never appear in application logs, traces, bootstrap files or receipts;
- be rotatable only through an explicit administrative operation.

A future OAuth client, delegated token or `azp`-based identity may replace this credential after the
non-human identity model is approved. That evolution is outside Version 1.

## 10.1 Request-Scoped Dependency

FastAPI shall use a typed dependency to:

- authenticate the EVDriver through the existing identity dependency;
- require all simulation headers together;
- validate header formats;
- load the `SimulationRun`;
- verify the run credential;
- require `RUNNING` status;
- require the EVDriver association;
- normalize `X-Simulated-At` to UTC;
- validate the logical window;
- create an internal `SimulationRequestContext`.

HTTP middleware may enrich correlation, logs and traces, but shall not be the authoritative source
of simulation authorization or business context.

The internal context shall contain at least:

- `simulation_run_id`;
- `simulation_event_id`;
- normalized `simulated_at`;
- authenticated EVDriver ID.

Raw header values shall not be passed directly to the domain.

---

# 11. Logical Time

The Simulation Engine controls logical time. The Backend API validates and applies it.

For a normal request:

```text
request clock = SystemClock
```

For an authorized simulated request:

```text
request clock = FixedClock(simulated_at)
```

The existing `Clock` protocol shall be reused. Domain services shall not inspect a simulation flag;
they shall continue to call `clock.now()`.

Any direct construction of `SystemClock` in simulated operational paths, including Telemetry receipt
time where operational time is intended, shall be replaced by request-scoped injection.

Real processing timestamps shall continue to use the actual backend clock where appropriate.

## 11.1 Window

For every new successful Simulation Event:

```text
logical_start_at <= simulated_at <= logical_end_at
```

Both boundaries are inclusive in Version 1.

## 11.2 Monotonicity

For every new successful Simulation Event:

```text
simulated_at >= last_accepted_simulated_at
```

An equal timestamp is valid. A lower timestamp shall be rejected.

`last_accepted_simulated_at` advances only when a new mutable event is successfully committed.
Domain rejection and technical rollback do not advance it in Version 1.

## 11.3 Global Temporal Barrier

The simulator shall not issue distinct timestamps concurrently.

It shall:

- process all events at one timestamp;
- wait until that timestamp group reaches a terminal local result;
- only then advance to a later timestamp.

Concurrency is permitted only among events with exactly the same `simulated_at`, preferably when
they do not contend for the same Vehicle, Reservation, Connector or Charging Session.

This rule prevents a later timestamp from acquiring the run lock first and causing an earlier event
to be correctly rejected as stale.

## 11.4 Equal Timestamps

Multiple events may share exactly the same timestamp. This reflects legitimate simultaneous
activity and avoids imposing an artificial sequence contract.

When causal order matters, the simulator shall either:

- wait for the prior operation and use a slightly later timestamp; or
- serialize the events locally before sending them.

No `X-Simulation-Sequence` header is required in Version 1.

---

# 12. Simulated Operation Allowlist

Simulation context shall be accepted only on an explicit allowlist.

Version 1 includes:

- create Reservation;
- cancel Reservation;
- activate Charging Session from a Reservation;
- complete Charging Session;
- submit one Telemetry sample;
- submit an atomic Telemetry batch.

Equivalent current routes are:

```text
POST /reservations
POST /reservations/{reservationId}/cancel
POST /reservations/{reservationId}/charging-session
POST /charging-sessions/{sessionId}/complete
POST /charging-sessions/{sessionId}/telemetry
POST /charging-sessions/{sessionId}/telemetry/batch
```

Read operations shall use the normal API contracts without a logical-time context. Temporal query
filters remain explicit query parameters and shall not silently depend on simulation headers.

The following mutations are outside the allowlist:

- User creation or mutation;
- Vehicle creation or mutation;
- Facility mutation;
- Station or Connector mutation;
- `SimulationRun` administration by an EVDriver;
- Dataset Export administration;
- Analytics or Prediction publication;
- unrelated administrative operations.

Vehicles, Users and infrastructure shall be created before the run by an administrator.

Reservation rescheduling is deferred unless required by a later approved scenario. Version 1 may
represent a behavioral retry by creating a new Reservation attempt after a rejected request.

A simulation header on an unsupported endpoint shall return a documented error such as
`SIMULATION_CONTEXT_NOT_SUPPORTED`.

---

# 13. Resource Authorization

The request dependency validates the run and EVDriver before payload processing. Resource-specific
authorization occurs after resolving the target hierarchy.

The Facility shall be derived as follows:

- Reservation creation: Connector -> Station -> Facility;
- Reservation cancellation or Session activation: Reservation -> Connector -> Station -> Facility;
- Session completion or Telemetry: Charging Session -> Connector -> Station -> Facility.

The resolved Facility shall belong to the run.

The backend shall reject:

- a Facility outside the run;
- a Station or Connector outside an authorized Facility;
- an EVDriver outside the run;
- a Session or Reservation belonging to another run;
- a simulated Session derived from a real Reservation;
- a Session in run A derived from a Reservation in run B.

A trusted run credential never grants authority beyond the EVDriver token and associated Facilities.

---

# 14. Provenance

`Reservation` shall have:

```text
simulation_run_id UUID NULL
```

`ChargingSession` shall have:

```text
simulation_run_id UUID NULL
```

`NULL` represents a non-simulated operation. Existing rows remain `NULL` after migration.

For an accepted simulated Reservation, the backend shall set `simulation_run_id` from the validated
request context. The value shall not be accepted from the client payload.

For a simulated Charging Session, the backend shall copy `simulation_run_id` exclusively from the
Reservation. It shall validate that the request context names the same run.

Telemetry shall not receive a new provenance column in Version 1. Its origin is derived through:

```text
Telemetry -> ChargingSession.simulation_run_id
```

Provenance is immutable. It shall not be added, removed or transferred after creation.

Version 1 does not automatically hide simulated data from all existing reads. Existing Analytics,
Dataset Export, administrative reads and Domain Events may include synthetic activity. Future
specifications may add explicit origin filters and retention rules.

Facilities used for accelerated simulation should be dedicated to synthetic operation. This is an
operational requirement for Version 1 because sharing Connectors with real traffic can produce
invalid temporal interactions even when provenance is preserved.

---

# 15. Idempotency and SimulationEventReceipt

Every allowed simulated mutation shall require one stable `X-Simulation-Event-Id`.

The logical idempotency key is:

```text
simulation_run_id + operation + simulation_event_id
```

`operation` shall be a stable domain-oriented code, for example:

```text
RESERVATION_CREATE
RESERVATION_CANCEL
SESSION_ACTIVATE
SESSION_COMPLETE
TELEMETRY_CREATE
TELEMETRY_BATCH_CREATE
```

For each new event, the backend shall compute a canonical SHA-256 digest over semantically relevant
content, including:

- operation;
- normalized route resource identifiers;
- normalized payload;
- normalized `simulated_at`;
- authenticated EVDriver ID;
- `simulation_run_id`.

Transient values such as bearer tokens, correlation IDs, trace IDs, User-Agent and the plaintext run
credential shall not be included.

## 15.1 Retry Behavior

When no receipt exists:

- validate monotonicity and domain rules;
- apply the operation;
- persist the successful receipt;
- advance the run clock;
- commit atomically.

When a receipt exists with the same digest:

- do not execute the domain operation again;
- return the stored canonical response and status;
- do not revalidate monotonicity against the older timestamp.

When the same idempotency key exists with a different digest:

- return `409 Conflict`;
- use a stable code such as `SIMULATION_EVENT_IDEMPOTENCY_CONFLICT`.

## 15.2 Successful Receipts Only

Version 1 persists receipts only for successful domain mutations.

A domain rejection:

- rolls back the attempted transaction;
- does not create a receipt;
- does not advance logical time.

Therefore a later retry of a rejected event is not guaranteed to reproduce the same rejection. This
trade-off is accepted to keep Version 1 transaction semantics bounded. Immutable receipts for domain
rejections are a future enhancement.

A technical failure shall roll back all state and leave no completed receipt.

## 15.3 Receipt Fields

`SimulationEventReceipt` shall contain at least:

- `id`;
- `simulation_run_id`;
- `simulation_event_id`;
- `operation`;
- authenticated EVDriver ID;
- `simulated_at`;
- canonical request digest;
- resource type and resource ID when applicable;
- response status;
- canonical response snapshot sufficient for retry;
- real `created_at` timestamp.

Receipts are immutable.

---

# 16. Transaction and Concurrency Requirements

The mutation, provenance, receipt and logical-clock advancement shall commit as one transaction.

The backend shall lock the relevant `SimulationRun` row using the database's transactional locking
mechanism equivalent to `SELECT ... FOR UPDATE`.

Inside one transaction, the coordinator shall:

1. lock the run;
2. search for an existing receipt;
3. return an identical receipt or reject a digest conflict;
4. validate `RUNNING` status and logical window;
5. validate monotonicity for a new event;
6. execute partitioned no-show reconciliation when required by the operational flow;
7. execute the existing domain service using the request-scoped clock;
8. persist operational changes and provenance;
9. persist the receipt;
10. update `last_accepted_simulated_at`;
11. commit once.

Repositories participating in simulated mutations shall not independently commit before this
coordinator completes. They shall support a shared transaction or Unit of Work and use `flush`
where intermediate database effects are required.

This transactional boundary is required for correctness. Separate commits for domain state,
receipt or logical clock are not acceptable.

Timestamp equality remains valid under the lock. The stored maximum remains unchanged when an equal
timestamp succeeds.

---

# 17. No-Show Reconciliation

The existing SCEP behavior reconciles overdue Reservations opportunistically rather than through a
scheduler. Version 1 shall preserve that domain behavior but partition it by provenance.

Normal reconciliation shall process only:

```text
simulation_run_id IS NULL
```

Simulated reconciliation shall process only:

```text
simulation_run_id = current SimulationRun
```

A simulated logical clock shall never mark a real Reservation or a Reservation from another run as
`NO_SHOW`.

Simulated reconciliation shall participate in the same coordinated transaction as the triggering
Simulation Event and shall not commit independently.

Run completion shall perform one final partitioned reconciliation at `logical_end_at` before
checking for active Charging Sessions.

Version 1 does not add a public endpoint for directly forcing `NO_SHOW`. The simulator creates a
Reservation and advances through later valid operations; SCEP applies its existing reconciliation
rules at the validated logical time.

---

# 18. Telemetry

Version 1 shall reuse the existing single-sample and batch Telemetry APIs.

The existing batch contract supports:

- one to 1,000 samples;
- atomic persistence;
- sample-level idempotency by existing Telemetry identity;
- rollback when any conflicting item invalidates the batch;
- `201` when at least one sample is created;
- `200` when all samples are identical retries.

A simulated Telemetry batch additionally has one Simulation Event Receipt for the whole HTTP
operation.

The batch shall be atomic with respect to:

- all Telemetry samples;
- the Simulation Event Receipt;
- logical-clock advancement.

Telemetry samples shall:

- belong to the target Charging Session;
- satisfy existing sample-order and session-window rules;
- use timestamps not later than the request's validated `simulated_at` when accumulated samples are
  submitted together;
- remain inside the run window;
- preserve the existing Telemetry contract and source semantics.

Telemetry generation is optional in a scenario. Reservations and completed Charging Sessions are
sufficient for occupancy experimentation; Telemetry supports energy metrics and pipeline realism.

---

# 19. External Scenario Contract

The behavioral scenario shall be external to SCEP and immutable for one run.

Global scenario configuration shall include at least:

- schema version;
- random seed;
- logical start and end matching the bootstrap;
- global Telemetry defaults;
- one behavior profile per configured EVDriver.

A run may preserve only opaque traceability references:

- `external_scenario_id`;
- `external_scenario_version`;
- `scenario_sha256`;
- `simulator_version`.

The Backend API shall not parse, validate or execute behavioral probabilities.

Before execution, the simulator shall verify that its scenario digest matches the value registered
on the run when that value is present.

---

# 20. Minimum Configurable EVDriver Behavior

Each EVDriver profile shall support the following minimum configuration.

## 20.1 Identity

- `driver_id` present in the bootstrap;
- external credential reference resolved outside the scenario file where practical;
- one or more pre-created Vehicles retrieved through the normal API.

## 20.2 Weekly Frequency

A minimum and maximum number of charging attempts per week.

Example:

```yaml
sessions_per_week:
  min: 2
  max: 5
```

## 20.3 Temporal Profile

Configurable relative weights for:

- weekday;
- hour of day;
- optional start-time jitter.

Weights need not sum to one; the simulator shall validate and normalize them.

## 20.4 Infrastructure Preference

The profile may define:

- Facility weights restricted to bootstrap Facilities;
- preferred Connector types;
- selection strategy such as weighted random or first eligible.

The simulator shall resolve current Stations and Connectors through the API. It shall not require a
frozen infrastructure snapshot.

## 20.5 Reservation Behavior

The profile may define:

- probability of using a Reservation;
- lead-time range;
- cancellation probability;
- no-show probability.

For the reference Version 1 scenario, Reservation probability should be `1.0` so all simulated
Charging Sessions preserve Reservation-rooted provenance.

Cancellation probability plus no-show probability shall not exceed one.

## 20.6 Charging Session Behavior

The profile shall define:

- minimum and maximum session duration;
- minimum and maximum power-utilization factor.

The simulator may derive energy from Connector power, elapsed duration and utilization. It shall not
generate physically impossible values under the current Telemetry rules.

## 20.7 Telemetry Behavior

Telemetry configuration may define:

- enabled or disabled;
- sampling interval;
- bounded power noise;
- batch size within the API limit.

Detailed battery state-of-charge curves are outside Version 1.

## 20.8 Failure Handling

The profile may define:

- whether to try another Connector;
- whether to try another Station;
- whether to try another Facility;
- maximum alternative attempts;
- rescheduling delay range;
- maximum rescheduling attempts;
- abandonment after exhaustion.

---

# 21. Event Planning and Causality

The simulator shall generate a deterministic event plan in increasing logical-time order.

Each EVDriver shall behave as one chronological user flow. Causally dependent events shall not be
sent speculatively in parallel.

Example:

```text
create Reservation
  -> wait for result
activate Charging Session
  -> wait for result
submit Telemetry batch or batches
  -> wait for result
complete Charging Session
```

EVDrivers may operate concurrently only within the global same-timestamp barrier.

When strict causal ordering is required, the simulator may use millisecond or microsecond timestamp
differences rather than a separate sequence field.

Each planned event shall contain locally:

- stable event ID;
- logical flow ID;
- EVDriver ID;
- operation;
- planned `simulated_at`;
- canonical payload;
- attempt number;
- dependency references.

---

# 22. Conflict, Retry and Abandonment Behavior

## 22.1 Expected Domain Rejection

Examples include:

- Connector unavailable;
- overlapping Reservation;
- Facility closed;
- Station or Connector inactive;
- no compatible resource.

The simulator may respond by:

1. refreshing current infrastructure;
2. trying another eligible Connector;
3. trying another Station in the Facility;
4. trying another authorized Facility;
5. rescheduling within configured limits;
6. abandoning the attempt.

Each alternative or rescheduled attempt is a new logical event with a new event ID.

## 22.2 Technical Retry

Timeouts, connection failures and retryable server errors shall reuse the same event ID and payload.
The successful receipt protects against duplicate mutation when the first response was lost.

Retry policy shall use bounded exponential backoff with jitter and shall not move to a later logical
timestamp until the current timestamp group is resolved.

## 22.3 Terminal Error

The simulator shall not attempt to bypass:

- invalid or expired run credential;
- run not `RUNNING`;
- EVDriver outside the run;
- Facility outside the run;
- stale or out-of-window logical time;
- idempotency digest conflict;
- malformed bootstrap or scenario;
- incompatible API contract.

These errors terminate the affected flow and normally the execution.

## 22.4 Abandonment

Local abandonment reasons may include:

- no capacity;
- no compatible Connector;
- alternative-attempt limit;
- rescheduling limit;
- insufficient remaining run window.

Abandonment is recorded in the simulator's report and does not create a backend resource.

---

# 23. Determinism and Reproducibility

For the same:

- scenario configuration;
- bootstrap;
- random seed;
- simulator version;

Version 1 shall generate the same initial event plan.

The simulator should derive stable per-EVDriver random streams so adding one driver does not
necessarily change all existing drivers' schedules.

Event IDs shall be stable across retry and may be generated deterministically from run ID, driver
ID, flow ID, operation and attempt number.

The simulator shall persist the generated plan or enough deterministic state to resume without
re-sampling completed decisions.

The plan is deterministic; final operational outcomes are best effort because current
infrastructure and concurrent domain conflicts may differ between executions.

The execution report shall distinguish planned determinism from observed backend outcomes.

---

# 24. Checkpoint and Resume

The simulator shall support local checkpointing.

A checkpoint shall preserve at least:

- run ID;
- scenario digest;
- simulator version;
- last completed timestamp barrier;
- completed and pending event IDs;
- unresolved retry state;
- dynamic alternative-resource decisions;
- next event position.

On restart, the simulator shall:

1. verify the run remains `RUNNING`;
2. verify bootstrap, scenario digest and simulator version compatibility;
3. reload the checkpoint;
4. resend any event whose final response is uncertain using the same event ID;
5. rely on backend idempotency;
6. continue without moving backward in logical time.

The simulator may pause locally while the backend run remains `RUNNING`.

---

# 25. Simulator Execution States and Report

Local simulator states are independent from backend run states and may include:

```text
READY
RUNNING
PAUSED
FINISHED
FAILED
CANCELLED_EXTERNALLY
```

After all events are resolved, the simulator shall produce a final report containing at least:

- run ID;
- scenario ID, version and digest;
- simulator version;
- real execution start and finish times;
- last processed logical timestamp;
- planned event count;
- successful event count;
- domain-rejected event count;
- technical retry count;
- abandoned flow count;
- terminal failure count;
- Reservations created and cancelled;
- Charging Sessions activated and completed;
- Telemetry samples submitted;
- unresolved warnings.

The report remains an external artifact in Version 1. It is not uploaded automatically to SCEP.

The simulator shall not create, start, complete or cancel the backend `SimulationRun`.

---

# 26. Persistence Model

Version 1 shall add tables equivalent to:

## 26.1 `simulation_runs`

- UUID primary key;
- lifecycle status with database constraint;
- logical window;
- nullable last accepted logical timestamp;
- secure credential hash;
- external scenario references;
- administrative creator foreign key;
- real audit timestamps;
- database checks for window and last accepted time.

## 26.2 `simulation_run_facilities`

- composite primary key `(simulation_run_id, facility_id)`;
- run foreign key with cascade limited to association cleanup;
- Facility foreign key with restrict behavior.

## 26.3 `simulation_run_evdrivers`

- composite primary key `(simulation_run_id, user_id)`;
- run foreign key with cascade limited to association cleanup;
- User foreign key with restrict behavior.

## 26.4 `simulation_event_receipts`

- UUID primary key;
- run foreign key with restrict behavior;
- actor foreign key with restrict behavior;
- operation and event ID;
- simulated time;
- request SHA-256;
- response status and snapshot;
- optional resource type and ID;
- real creation timestamp;
- unique constraint on `(simulation_run_id, operation, simulation_event_id)`.

## 26.5 Existing Tables

Add nullable, indexed run foreign keys to:

- Reservations;
- Charging Sessions.

Telemetry remains unchanged.

Recommended indexes include:

- `simulation_runs(status, created_at)`;
- `simulation_event_receipts(simulation_run_id, simulated_at)`;
- partial or equivalent index on Reservations by `(simulation_run_id, start_at)`;
- partial or equivalent index on Charging Sessions by `(simulation_run_id, status)`.

There shall be no public delete operation for `SimulationRun` in Version 1. Historical foreign keys
shall use restrict behavior.

---

# 27. Migration Compatibility

The migration shall:

- create all new tables and constraints;
- add nullable foreign keys to existing operational tables;
- leave every existing Reservation and Charging Session with `simulation_run_id = NULL`;
- avoid a data backfill;
- preserve all current API behavior;
- support clean downgrade where repository policy requires it;
- validate foreign keys, checks and indexes in migration tests.

Normal requests without simulation context shall continue to write `NULL` provenance and use
`SystemClock`.

---

# 28. Error Contract

Version 1 shall define stable machine-readable errors, including equivalents of:

```text
SIMULATION_CONTEXT_INCOMPLETE
SIMULATION_CONTEXT_NOT_SUPPORTED
SIMULATION_RUN_NOT_FOUND
SIMULATION_RUN_NOT_RUNNING
SIMULATION_RUN_CREDENTIAL_INVALID
SIMULATION_DRIVER_NOT_AUTHORIZED
SIMULATION_FACILITY_NOT_AUTHORIZED
SIMULATION_TIME_OUTSIDE_WINDOW
SIMULATION_TIME_REGRESSION
SIMULATION_EVENT_IDEMPOTENCY_CONFLICT
SIMULATION_SCENARIO_DIGEST_MISMATCH
SIMULATION_ACTIVE_SESSIONS_EXIST
```

Authentication and authorization errors shall avoid revealing whether an unrelated run or resource
exists.

The OpenAPI contract shall document required headers only on allowed operations.

---

# 29. Observability

Backend logs and traces for simulated requests shall include safe values equivalent to:

- simulation run ID;
- event ID;
- EVDriver ID;
- operation;
- simulated time;
- real processing time;
- idempotent replay indicator;
- outcome and HTTP status;
- correlation and trace IDs.

They shall never include:

- bearer tokens;
- plaintext run credential;
- passwords or credential references.

Backend metrics should include:

- active runs by status;
- successful simulated operations;
- idempotent replays and conflicts;
- stale-time and out-of-window rejections;
- authorization failures;
- lock and transaction latency;
- no-show reconciliation count by run;
- Telemetry batch count and sample count.

The simulator shall emit structured JSON logs containing run ID, event ID, driver ID, logical time,
operation, attempt, outcome, HTTP status and domain error code.

Dashboards and centralized simulator log shipping are future improvements.

---

# 30. Security Requirements

Version 1 shall ensure that:

- simulation headers alone grant no authority;
- every simulated mutation requires both an EVDriver JWT and valid run credential;
- the credential is checked against the named run;
- the EVDriver belongs to the run;
- the resolved Facility belongs to the run;
- the run is `RUNNING`;
- logical time is validated transactionally;
- client payloads cannot assign provenance;
- credentials are redacted from logs and traces;
- administrative lifecycle endpoints are unavailable to EVDrivers;
- bootstrap export does not expose secrets;
- completed and cancelled runs reject all simulated mutations;
- Facilities dedicated to simulation are used for accelerated execution.

The run credential is a Version 1 bridge, not the final non-human identity architecture.

---

# 31. Compatibility and Accepted Version 1 Side Effects

Because full synthetic-data isolation is deferred:

- Analytics may count simulated activity;
- Dataset Export may include simulated activity;
- administrative and Facility Operator queries may display simulated resources;
- Domain Events record simulated activity;
- the configured EVDriver sees its own simulated resources.

These effects are accepted only when simulation uses dedicated Facilities and EVDrivers as
recommended.

The following are not acceptable:

- no-show reconciliation altering normal or other-run Reservations;
- accepting logical time from an unauthenticated header set;
- using a Facility or EVDriver outside the run;
- sharing accelerated-time Connectors with real traffic;
- committing domain state, receipt and run clock separately;
- allowing provenance to be supplied or modified by a client.

Future improvements shall add explicit origin filters to operational reads, Analytics and Dataset
Export.

---

# 32. Testing Requirements

## 32.1 Unit Tests

Cover:

- lifecycle transitions;
- logical-window validation;
- association validation;
- run credential hashing and verification;
- fixed request clock;
- canonical request digest;
- provenance propagation;
- completion rules;
- scenario and bootstrap schema validation in the simulator.

## 32.2 API Tests

Cover:

- every administrative endpoint;
- bootstrap output;
- missing, partial and malformed headers;
- unsupported endpoint context;
- invalid run credential;
- EVDriver outside the run;
- Facility outside the run;
- completed or cancelled run;
- allowed normal requests without simulation context.

## 32.3 Logical-Time Tests

Cover:

- inclusive window boundaries;
- normalized offsets and UTC persistence;
- equal timestamps;
- stale timestamps;
- timestamp groups and barrier behavior;
- fixed clock use in Reservation, Session and Telemetry paths.

## 32.4 Idempotency Tests

Cover:

- first successful event;
- identical replay;
- divergent replay returning `409`;
- replay after client timeout;
- atomic rollback when receipt persistence fails;
- atomic rollback when domain persistence fails;
- restart behavior.

## 32.5 Concurrency Tests

Cover:

- row lock on the run;
- concurrent equal timestamps;
- distinct timestamps arriving inverted;
- duplicate event IDs;
- completion concurrent with mutation;
- contending Connector, Vehicle and Reservation operations.

## 32.6 No-Show Tests

Cover:

- simulated reconciliation affects only the current run;
- normal reconciliation affects only `NULL` provenance;
- another run is untouched;
- strict existing 15-minute boundary behavior;
- final completion reconciliation;
- rollback under coordinated transaction failure.

## 32.7 Telemetry Tests

Cover:

- existing single and batch contracts;
- 1,000-sample limit;
- atomic batch rollback;
- existing sample idempotency;
- Simulation Event Receipt for a batch;
- logical received time where applicable;
- sample timestamps relative to Session and request time.

## 32.8 Migration Tests

Cover:

- upgrade and downgrade policy;
- old rows remaining `NULL`;
- foreign keys;
- checks;
- unique constraints;
- recommended indexes;
- deletion restrictions.

## 32.9 Regression Tests

All normal Reservation, Charging Session, Telemetry, no-show, Analytics and Dataset Export tests
shall continue to pass without simulation headers.

---

# 33. Acceptance Criteria

Version 1 is accepted when:

1. an administrator can create, configure, start, inspect, complete and cancel a run;
2. the bootstrap exports only the approved minimal identifiers and metadata;
3. an EVDriver cannot use simulation headers without the valid run credential;
4. a valid simulated request receives the configured logical time through the existing `Clock`;
5. a request outside the logical window is rejected;
6. a timestamp lower than the last successful event is rejected;
7. multiple events with the same timestamp are accepted;
8. successful retries return the prior canonical result without duplicate mutation;
9. divergent reuse of an event ID returns `409`;
10. Reservation and Charging Session provenance is written only by the backend;
11. a Session inherits the same run as its Reservation;
12. Telemetry provenance is derivable from the Session;
13. no-show reconciliation never crosses real-data or run boundaries;
14. domain mutation, receipt and logical-clock advancement are atomic;
15. the existing Telemetry batch endpoint works under simulation context;
16. the simulator preserves chronological flow per EVDriver and timestamp barriers globally;
17. checkpoint resume safely replays uncertain successful events;
18. run completion rejects active simulated Sessions;
19. no existing normal flow requires simulation headers or changes behavior;
20. the external simulator remains deployable and executable independently from the Backend API.

---

# 34. Recommended Implementation Sequence

1. amend ADR-005 to clarify backend-visible simulation context;
2. add migrations, models and `SimulationRun` lifecycle;
3. add run-scoped credential generation and validation;
4. add typed request context and request-scoped `Clock`;
5. establish a coordinated transaction or Unit of Work;
6. partition no-show reconciliation;
7. integrate Reservation create and cancel;
8. integrate Session activation and completion;
9. integrate Telemetry single and batch paths;
10. add bootstrap and completion validation;
11. implement the external simulator, schemas, checkpoints and reporting;
12. add observability, security and complete regression tests;
13. generate a reference synthetic dataset for SPEC-012 validation.

---

# 35. Future Evolution

Future versions may add:

- permanent authenticated simulator-client identity;
- OAuth delegation or token exchange;
- immutable receipts for domain rejections;
- synthetic-data filters in operational APIs;
- Dataset Export selection by run;
- Analytics origin separation;
- retention and cleanup policies;
- uploaded execution reports;
- explicit rescheduling support;
- maintenance and equipment-failure scenarios;
- OCPP and hardware-in-the-loop integration;
- electrical-grid constraints;
- dynamic pricing, weather and mobility inputs;
- distributed simulation workers;
- richer battery and charging-curve models;
- learned or adaptive behavioral agents.

These capabilities shall preserve the external Simulation Engine boundary and shall not move
behavioral simulation into the transactional domain.

---

# 36. Decision Summary

SPEC-013 Version 1 introduces a controlled backend context for an otherwise external Digital Twin.
The simulator owns behavior, deterministic planning and logical-clock progression. SCEP owns
identity, authorization, temporal validation, domain invariants, provenance, persistence and
idempotency.

The central contract is:

```text
external simulator controls scenario time and behavior
backend validates run, scope, order and business invariants
successful domain change + receipt + logical-clock advancement commit atomically
```

This design creates representative synthetic operational data while preserving the SCEP
architecture, existing domain model and future compatibility with real external clients.