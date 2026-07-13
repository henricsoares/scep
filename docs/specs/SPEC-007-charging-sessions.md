# SPEC-007 — Charging Sessions

## Smart Charging Experimentation Platform (SCEP)

**Status:** Draft

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

This specification defines the Charging Session capability of the Smart Charging Experimentation
Platform (SCEP). A Charging Session represents the effective utilization of a Connector by a
Vehicle, whereas a Reservation allocates future access to that Connector.

Telemetry, energy measurements, OCPP communication, billing and analytics remain outside the scope of this specification.

---

# 2. Scope

This specification includes:

- Charging Session Aggregate;
- session activation;
- session completion;
- Reservation integration;
- Connector status transitions;
- authorization;
- REST API;
- persistence;
- concurrency;
- OpenAPI;
- metrics;
- testing requirements.

---

## Out of Scope

The following capabilities are intentionally deferred.

- direct or otherwise unreserved Charging Sessions;
- OCPP communication;
- telemetry ingestion;
- energy measurements;
- charging power;
- battery information;
- pricing;
- billing;
- payments;
- notifications;
- domain events;
- analytics;
- AI;
- Digital Twin execution.

These capabilities require later specifications before they enter the platform scope.

---

# 3. Relationship with Reservations

Charging Sessions execute Reservations. Every Charging Session shall originate from exactly one
valid Reservation, and one Reservation may originate at most one Charging Session.

The relationship is:

```text
Reservation 1 -------- 0..1 ChargingSession
```

Charging Sessions shall never exist without an associated Reservation. Activating a Reservation
therefore creates its Charging Session.

---

# 4. Domain Model

The Charging Session Aggregate represents the execution of a Reservation.

A Charging Session records when a Vehicle actually begins and finishes using a Connector.

The Aggregate owns:

- session lifecycle;
- operational timestamps;
- Reservation activation;
- Reservation completion;
- Connector status transitions.

Charging Sessions do not own telemetry, energy measurements or charging commands.

---

## Charging Session

```text
ChargingSession

id

reservation_id

owner_id

vehicle_id

connector_id

status

started_at
ended_at

created_at
updated_at
```

---

## Attributes

### id

Unique identifier of the Charging Session.

Immutable.

---

### reservation_id

Reference to the Reservation that originated the Charging Session.

Mandatory.

Immutable.

At most one Charging Session may exist for a Reservation.

---

### owner_id

Authenticated Identity that owns the Reservation.

Derived from the Reservation.

Immutable.

---

### vehicle_id

Vehicle assigned to the Reservation.

Derived from the Reservation.

Immutable.

---

### connector_id

Connector assigned to the Reservation.

Derived from the Reservation.

Immutable.

---

### status

Charging Session lifecycle state.

Supported values:

```text
ACTIVE
COMPLETED
```

---

### started_at

Timestamp assigned when Reservation activation successfully creates the Charging Session. It does
not represent a metering or OCPP signal.

Immutable.

---

### ended_at

Timestamp indicating when charging finished.

Null while ACTIVE.

Immutable after completion.

---

### created_at

Creation timestamp.

Immutable.

---

### updated_at

Last modification timestamp.

Automatically maintained.

---

# 5. Ubiquitous Language

## Charging Session

Operational execution of one Reservation.

---

## Active Charging Session

A Charging Session whose status is:

```text
ACTIVE
```

An Active Charging Session exclusively occupies:

- one Connector;
- one Vehicle.

---

## Completed Charging Session

A historical Charging Session.

Completed Charging Sessions never block future Reservations or Charging Sessions.

---

## Session Activation

Operation that creates a Charging Session from an eligible Reservation.

Activation also transitions the Reservation to ACTIVE.

---

## Session Completion

Operation that finishes an ACTIVE Charging Session.

Completion also transitions the Reservation to COMPLETED.

---

## Connector Occupancy

A Connector occupied by an ACTIVE Charging Session.

The Connector operational status becomes:

```text
Charging
```

---

## Session Ownership

Charging Sessions inherit ownership from their Reservation.

Ownership cannot be reassigned.

---

# 6. Charging Session Lifecycle

Charging Sessions support the following lifecycle.

```text
ACTIVE

↓

COMPLETED
```

No additional states exist in this version.

---

## Creation

Charging Sessions are created exclusively by Reservation activation. Applications shall never
create standalone or unreserved Charging Sessions.

---

## Completion

Charging Sessions terminate through explicit completion.

Automatic completion is outside the scope of this specification.

---

## Historical Records

Completed Charging Sessions remain permanently available for:

- operational history;
- auditing;
- future telemetry association;
- future analytics.

Charging Sessions shall never be physically deleted.

---

# 7. Reservation Integration

Reservation activation creates a Charging Session.

The transition is atomic.

```text
Reservation

CONFIRMED

↓

ACTIVE

+

ChargingSession

ACTIVE
```

Reservation completion occurs simultaneously with Charging Session completion.

```text
ChargingSession

ACTIVE

↓

COMPLETED

+

Reservation

ACTIVE

↓

COMPLETED
```

Charging Sessions shall never activate:

- CANCELLED Reservations;
- LATE_CANCELLED Reservations;
- NO_SHOW Reservations;
- COMPLETED Reservations;
- ACTIVE Reservations.

Attempting to activate any of these states shall fail.

---

# 8. Business Rules

## BR-001 — Reservation Requirement

Every Charging Session shall originate from exactly one valid Reservation.

Charging Sessions without a Reservation are outside the scope of this specification.

---

## BR-002 — Eligible Reservation

A Charging Session may only be created when the Reservation:

- exists;
- is visible to the requesting Authenticated Identity;
- is in the `CONFIRMED` state;
- is within the Reservation activation window defined by SPEC-006;
- satisfies the infrastructure eligibility and activation invariants defined by SPEC-006;
- has not originated another Charging Session.

A Connector whose `Reserved` status represents the Reservation being activated remains eligible.
An `OutOfService` Connector or a Connector already in `Charging` does not. This interpretation uses
the Connector statuses owned by SPEC-004 and does not permit direct Charging Sessions.

---

## BR-003 — Ownership

The Authenticated Identity shall own the Reservation unless the Platform Administrator permission
defined by this specification applies.

Ownership is inherited by the Charging Session.

---

## BR-004 — Vehicle Consistency

The Charging Session shall inherit the Vehicle assigned to the Reservation.

Vehicle assignment shall never change after session creation.

---

## BR-005 — Connector Consistency

The Charging Session shall inherit the Connector assigned to the Reservation.

Connector assignment shall never change after session creation.

---

## BR-006 — One Session per Reservation

A Reservation shall originate at most one Charging Session over its entire lifecycle.

Attempts to activate an already activated Reservation shall fail.

---

## BR-007 — Active Session per Connector

At any instant, a Connector shall participate in at most one ACTIVE Charging Session.

Concurrent activation requests shall never create multiple ACTIVE sessions for the same Connector.

---

## BR-008 — Active Session per Vehicle

A Vehicle shall participate in at most one ACTIVE Charging Session.

Concurrent activation requests shall never create multiple ACTIVE sessions for the same Vehicle.

---

## BR-009 — Connector Status

Immediately after successful activation, the Connector status shall become:

```text
Charging
```

Immediately after successful completion, the Connector operational status shall transition
according to the current operational conditions defined by SPEC-004.

Typical transitions include:

```text
Charging → Available
```

or

```text
Charging → Reserved
```

or

```text
Charging → OutOfService
```

The resulting status depends on the Connector operational context. SPEC-007 does not introduce
additional Connector statuses.

---

## BR-010 — Atomic Activation

Charging Session creation, Reservation activation and the Connector transition to `Charging` shall
occur within the same transaction.

The following state shall never be observable:

```text
ChargingSession ACTIVE

Reservation CONFIRMED
```

Likewise, the following shall never be observable:

```text
Reservation ACTIVE

without ChargingSession
```

---

## BR-011 — Atomic Completion

Charging Session completion, Reservation completion and the Connector transition away from
`Charging` shall occur within the same transaction. One concurrent completion may succeed; later
attempts shall observe the terminal Charging Session and fail without changing persisted state.

---

## BR-012 — Historical Preservation

Completed Charging Sessions remain permanently available.

Historical records shall never be physically deleted.

---

## BR-013 — Immutable Identity

The following attributes are immutable after Charging Session creation:

- reservation_id;
- owner_id;
- vehicle_id;
- connector_id;
- started_at.

Only:

- status;
- ended_at;
- updated_at;

may change during the lifecycle.

---

## BR-014 — UTC Time

All persisted timestamps shall use timezone-aware UTC values.

Public APIs shall expose ISO-8601 timestamps including explicit timezone offsets.

---

# 9. Authorization

Authorization combines:

- Authenticated Identity;
- account type;
- assigned roles;
- ownership;
- Facility scope.

---

## Platform Administrator

The `PlatformAdministrator` Role may:

- activate any eligible Reservation;
- complete any ACTIVE Charging Session;
- view every Charging Session.

---

## Human Account

May:

- activate owned eligible Reservations;
- complete owned ACTIVE Charging Sessions;
- list owned Charging Sessions;
- retrieve owned Charging Sessions.

---

## Technical Client

Technical Client accounts follow the same ownership workflow as Human accounts.

They may:

- activate owned eligible Reservations;
- complete owned ACTIVE Charging Sessions;
- inspect owned Charging Sessions.

Technical Clients shall not administer infrastructure.

---

## Facility Operator

The `FacilityOperator` Role may:

- list Charging Sessions associated with managed Facilities;
- retrieve Charging Sessions associated with managed Facilities;
- complete ACTIVE Charging Sessions whose Connector belongs, through its Charging Station, to a
  managed Facility.

Facility Operators shall not activate Reservations on behalf of users.

---

## Researcher and Data Scientist

The `Researcher` and `DataScientist` Roles grant no Charging Session permissions by themselves.
An Authenticated Identity holding either Role may still use the ownership-based Human workflow for
its own Reservation and Charging Session. Future analytical specifications may add read-only
visibility without granting activation or completion of another owner's resources.

---

# 10. REST API

All Charging Session endpoints require authentication. Resource visibility and concealment follow
SPEC-005 and SPEC-006.

## Create Charging Session

```http
POST /reservations/{reservationId}/charging-session
```

Creates a Charging Session from an eligible Reservation.

Successful activation returns:

```http
201 Created
```

The response contains the newly created Charging Session.

---

Possible responses:

```text
201 Created
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Unprocessable Entity
```

`409 Conflict` applies when Reservation uniqueness or ACTIVE Connector or Vehicle exclusivity is
violated, including a concurrent duplicate activation. `422 Unprocessable Entity` applies when the
Reservation is outside its activation window, infrastructure is ineligible, or the lifecycle
request is otherwise invalid. Missing or concealed resources return `404 Not Found`.

---

## List Charging Sessions

```http
GET /charging-sessions
```

Returns Charging Sessions visible to the Authenticated Identity.

Pagination shall follow existing platform conventions.

---

## Retrieve Charging Session

```http
GET /charging-sessions/{sessionId}
```

Returns one visible Charging Session.

Invisible resources shall be concealed using:

```http
404 Not Found
```

---

## Complete Charging Session

```http
POST /charging-sessions/{sessionId}/complete
```

Completes an ACTIVE Charging Session.

Successful completion returns:

```http
200 OK
```

Attempting to complete a terminal Charging Session shall fail with:

```http
422 Unprocessable Entity
```

For concurrent completion requests, exactly one request may complete the ACTIVE Charging Session;
requests that observe it as COMPLETED return `422 Unprocessable Entity`.

---

## Connector Sessions

```http
GET /connectors/{connectorId}/charging-sessions
```

Returns Charging Sessions visible to the Authenticated Identity for the specified Connector.

---

## Vehicle Sessions

```http
GET /vehicles/{vehicleId}/charging-sessions
```

Returns Charging Sessions visible to the Authenticated Identity for the specified Vehicle.

---

# 11. Persistence

Charging Sessions are persisted independently from Reservations.

The persistence model shall include, at minimum:

```text
charging_sessions

id

reservation_id

owner_id

vehicle_id

connector_id

status

started_at
ended_at

created_at
updated_at
```

The persistence model shall enforce:

- primary key;
- Reservation foreign key and uniqueness across all Charging Sessions;
- Authenticated Identity owner foreign key;
- Vehicle foreign key;
- Connector foreign key;
- valid status constraint;
- timezone-aware timestamps.

The implementation shall prevent:

- multiple Charging Sessions for the same Reservation;
- multiple ACTIVE Charging Sessions for the same Vehicle;
- multiple ACTIVE Charging Sessions for the same Connector.

The Reservation uniqueness guarantee shall apply to historical rows as well as ACTIVE rows. Vehicle
and Connector exclusivity applies only to ACTIVE rows. The chosen locking and constraint strategy
is implementation-specific, provided externally observable behavior satisfies this specification.

---

# 12. Observability

Charging Session operations shall expose operational metrics consistent with the platform
observability model.

Metrics shall never include high-cardinality labels such as:

- session identifiers;
- reservation identifiers;
- vehicle identifiers;
- connector identifiers;
- user identifiers;
- email addresses.

At minimum, the implementation shall expose:

- Charging Sessions activated;
- Charging Sessions completed;
- Charging Session activation failures;
- Charging Session completion failures;
- Charging Session conflicts.

Structured logs shall be emitted for significant lifecycle operations.

At minimum:

- Charging Session activated;
- Charging Session completed;
- activation denied;
- completion denied;
- activation conflict.

Logs shall follow the platform structured logging conventions and include:

- request identifier;
- correlation identifier;
- trace identifier;
- span identifier;

when available.

Sensitive information shall never be written to logs.

---

# 13. OpenAPI

The generated OpenAPI documentation shall include:

- Charging Session schemas;
- Charging Session status enumeration;
- request and response examples;
- authentication requirements;
- authorization responses;
- conflict responses;
- validation responses.

Bearer authentication shall be declared for every protected endpoint.

At minimum, example payloads shall be provided for:

- successful Charging Session activation;
- successful Charging Session completion;
- Reservation already activated;
- Connector conflict;
- Vehicle conflict.

---

# 14. Acceptance Criteria

The implementation shall satisfy the following acceptance criteria.

---

## Charging Session

- Charging Session Aggregate implemented.
- Reservation is mandatory.
- At most one Charging Session per Reservation, and every Charging Session references exactly one
  Reservation.
- ACTIVE lifecycle implemented.
- COMPLETED lifecycle implemented.
- Historical records preserved.

---

## Reservation Integration

- Eligible Reservation activates successfully.
- Reservation transitions from CONFIRMED to ACTIVE.
- Charging Session is created atomically.
- Charging Session completion transitions Reservation to COMPLETED.
- Invalid Reservation states cannot be activated.

---

## Authorization

- Platform Administrator permissions validated.
- Human ownership validated.
- Technical Client ownership validated.
- Facility Operator managed-Facility completion permission validated.
- Researcher and Data Scientist ownership behavior validated.

---

## Connector Status

- Connector transitions to `Charging` after activation.
- Connector leaves `Charging` after completion.
- Connector status remains consistent after failures.

---

## Concurrency

- One Charging Session per Reservation across all lifecycle states.
- One ACTIVE Charging Session per Connector.
- One ACTIVE Charging Session per Vehicle.
- Concurrent activation requests cannot violate exclusivity.
- Concurrent completion requests remain consistent.

---

## Persistence

- Foreign keys enforced.
- Status constraints enforced.
- UTC timestamps persisted.
- Historical data preserved.
- Concurrency guarantees validated.

---

## API

- All endpoints documented.
- Authentication enforced.
- Ownership enforced.
- Concealment rules respected.
- Stable HTTP error contracts implemented.

---

## Observability

- Metrics exposed.
- Structured logs emitted.
- OpenAPI updated.

---

# 15. Testing Requirements

The implementation shall include automated tests covering:

---

## Domain

- Charging Session creation.
- Charging Session completion.
- Valid lifecycle transitions.
- Invalid lifecycle transitions.
- Immutable attributes.

---

## Reservation Integration

- Activation from CONFIRMED Reservation.
- Activation when the Connector is `Reserved` by that Reservation.
- Completion of ACTIVE Reservation.
- Invalid Reservation states.
- Duplicate Charging Session rejection.

---

## Authorization

- Platform Administrator.
- Human owner.
- Technical Client.
- Facility Operator.
- Researcher and Data Scientist ownership behavior.
- Concealment behavior.

---

## API

- Charging Session activation.
- Charging Session completion.
- Listing.
- Retrieval.
- Pagination.
- Validation failures.
- Authentication failures.
- Authorization failures.

---

## Persistence

- Database migration and schema constraints.
- Foreign keys.
- Reservation relationship.
- Historical preservation.

---

## PostgreSQL Concurrency

Real PostgreSQL integration tests shall validate:

- concurrent activation for the same Reservation;
- concurrent activation for the same Connector;
- concurrent activation for the same Vehicle;
- concurrent completion requests.

Concurrent execution shall never produce more than one Charging Session for the same Reservation or
more than one ACTIVE Charging Session for the same Connector or Vehicle.

---

## Docker Compose

A complete smoke test shall validate:

- automatic migrations;
- backend health;
- Charging Session activation;
- Charging Session completion;
- Connector status;
- Reservation lifecycle;
- OpenAPI;
- Prometheus metrics;
- Grafana dashboards;
- existing Reservation functionality remains unaffected.

---

# 16. Specification Summary

This specification introduces the operational execution layer of the Smart Charging Experimentation Platform.

Reservations allocate future access to charging infrastructure.

Charging Sessions represent the actual use of that allocation.

Together, SPEC-006 and SPEC-007 establish a complete scheduling and execution workflow:

```text
Reservation

CONFIRMED

        │

POST /reservations/{reservationId}/charging-session

        │

Reservation ACTIVE + ChargingSession ACTIVE

        │

POST /charging-sessions/{sessionId}/complete

        │

ChargingSession COMPLETED + Reservation COMPLETED
```

Later specifications may build on this model but shall preserve its lifecycle, ownership and
transactional guarantees.

---

# 17. Dependencies

Charging Sessions depend on the capabilities introduced by previous specifications.

The implementation requires:

- SPEC-003 — Facilities
- SPEC-004 — Charging Stations
- SPEC-005 — Identity and Access
- SPEC-006 — Reservations

Charging Sessions shall not redefine concepts already owned by those specifications.

In particular:

- authentication and authorization remain governed by SPEC-005;
- Connector statuses remain governed by SPEC-004;
- Reservation ownership and activation windows remain governed by SPEC-006.

Whenever a rule is already defined by an earlier specification, that specification takes
precedence unless this specification explicitly narrows the Charging Session scope.

---

# End of Specification
