# SPEC-006 — Reservations

**Status:** Draft

**Owner:** Henrique Soares

**Category:** Functional Specification

**Depends on:**

- SPEC-003 — Facilities
- SPEC-004 — Charging Stations
- SPEC-005 — Identity and Access

**Enables:**

- SPEC-007 — Charging Sessions
- SPEC-008 — Telemetry
- SPEC-009 — Domain Events
- SPEC-010 — Analytics

---

# 1. Overview

This specification defines the Reservation capability of the Smart Charging Experimental Platform (SCEP).

A Reservation grants an authenticated identity the exclusive right to use a specific charging Connector during a scheduled time window.

The Reservation capability is responsible for:

- preventing reservation conflicts;
- protecting Connector availability;
- supporting fair resource allocation;
- enabling future Charging Sessions;
- enabling Digital Twin simulations;
- providing reliable historical reservation data.

Reservations are independent domain objects with their own lifecycle and business rules.

They do **not** start charging.

Charging begins only when a valid Charging Session is created.

---

# 2. Goals

The Reservation capability shall:

- allow authenticated users to reserve Connectors;
- prevent overlapping reservations;
- support Human and Technical Client identities;
- support multiple Vehicles owned by the same user;
- allow early charging when infrastructure is available;
- detect reservation no-shows;
- support late cancellations while immediately releasing infrastructure;
- preserve historical reservation information;
- provide a consistent foundation for Charging Sessions.

---

# 3. Scope

This specification defines:

- Reservation Aggregate;
- Reservation lifecycle;
- Reservation business rules;
- Reservation validation rules;
- Reservation authorization rules;
- REST API;
- persistence model;
- OpenAPI requirements.

This specification intentionally avoids implementation details such as ORM mapping, messaging technologies or infrastructure decisions.

---

# 4. Out of Scope

The following capabilities are intentionally excluded:

- Charging Session execution;
- energy delivery;
- charger communication protocols;
- OCPP;
- telemetry ingestion;
- billing;
- pricing;
- payment processing;
- reservation extensions;
- reservation waiting lists;
- recurring reservations;
- notifications;
- emails;
- push notifications;
- SMS;
- calendar synchronization;
- predictive reservation optimization;
- Domain Events implementation;
- analytics.

---

# 5. Business Motivation

Public charging infrastructure is a shared and limited resource.

Reservations allow users to plan charging activities while ensuring infrastructure availability.

A reservation guarantees exclusive access to a Connector during a defined period, but charging itself only begins when the user starts a Charging Session.

The Reservation capability also provides the operational basis for:

- no-show detection;
- Digital Twin simulations;
- infrastructure utilization metrics;
- future scheduling algorithms.

---

# 6. Ubiquitous Language

## Reservation

A scheduled exclusive allocation of one Connector to one Vehicle during a defined time interval.

---

## Reservation Owner

The authenticated identity responsible for the Reservation.

A Reservation Owner may be:

- Human account;
- Technical Client account.

---

## Vehicle

A logical representation of a vehicle owned by a Reservation Owner.

Reservations belong to Vehicles rather than directly to users.

This allows one owner to reserve multiple Connectors simultaneously for different vehicles.

---

## Connector

The physical charging interface where charging occurs.

Reservations are created for Connectors.

Reservations are **not** created directly for Facilities or Charging Stations.

---

## Early Start

The ability to start charging before the official reservation start time.

Early Start is allowed only when:

- the Connector is available;
- no Charging Session is currently active;
- the configured Early Start window has begun.

---

## Grace Period

Additional time after the scheduled reservation start during which charging may still begin without being classified as a No-Show.

---

## No-Show

A Reservation that was never activated before the Grace Period expired.

---

## Late Cancellation

A Reservation cancelled after the normal cancellation window but before charging actually begins.

Late Cancellation releases the Connector immediately while preserving historical information.

---

## Back-to-Back Reservation

Two Reservations scheduled consecutively without any gap.

Example:

```text
09:00 ───── 10:00

10:00 ───── 11:00
```

Back-to-Back Reservations are valid.

The API may warn users that the previous vehicle could still be disconnecting.

---

# 7. Domain Model

The Reservation capability introduces the following primary concepts.

```text
Identity
    │
    ├── owns
    ▼
Vehicle
    │
    ├── creates
    ▼
Reservation
    │
    ├── reserves
    ▼
Connector
    │
    └── belongs to
        Charging Station
            │
            └── belongs to
                Facility
```

Reservation is the Aggregate Root.

Connector, Charging Station and Facility remain external aggregates referenced by identifier.

Charging Sessions are outside the scope of this specification but will later activate Reservations.

Vehicle represents the physical or simulated electric vehicle participating in charging operations.

Vehicle is introduced as a supporting domain entity for Reservations.

This specification requires only the information necessary to uniquely identify the vehicle and its owner.

Future specifications may extend Vehicle with battery, charging capability, manufacturer, model and simulation-related attributes without modifying the Reservation Aggregate.

---

# 8. Architectural Principles

The Reservation Aggregate shall:

- encapsulate reservation lifecycle rules;
- validate scheduling conflicts;
- prevent invalid state transitions;
- remain independent from Charging Session implementation;
- expose business behavior instead of persistence behavior.

Persistence technology shall not influence the domain model.

Reservation business rules must remain deterministic and independently testable.

---

# 9. Reservation Aggregate

Aggregate Root:

```text
Reservation
```

Primary attributes:

```text
Reservation

id

owner_id

vehicle_id

connector_id

start_at

end_at

status

created_at

updated_at

activated_at

completed_at

cancelled_at

late_cancelled_at

no_show_at
```

The Reservation Aggregate owns:

- lifecycle transitions;
- scheduling validation;
- overlap validation;
- cancellation policy;
- no-show detection.

External aggregates are referenced only by identifier.

# 10. Reservation Lifecycle

A Reservation follows a deterministic lifecycle.

The initial state is always:

```text
CONFIRMED
```

From that point, the Reservation may transition according to the following state machine.

```text
                    +----------------+
                    |   CONFIRMED    |
                    +----------------+
                     │   │      │
                     │   │      │
 Charging Session    │   │      │
 starts              │   │      │
                     │   │      │
                     ▼   ▼      ▼
               +--------+   +----------------+
               | ACTIVE |   | CANCELLED      |
               +--------+   +----------------+
                    │
                    │
                    │ Charging Session ends
                    ▼
             +--------------+
             | COMPLETED    |
             +--------------+

CONFIRMED
      │
      │ Grace Period expires
      ▼
+---------------+
| NO_SHOW       |
+---------------+

CONFIRMED
      │
      │ Cancelled inside late window
      ▼
+-------------------+
| LATE_CANCELLED    |
+-------------------+
```

Only the transitions defined by this specification are valid.

No implementation may introduce additional lifecycle transitions without updating this specification.

---

# 11. Reservation Status

The Reservation Aggregate supports the following states.

## CONFIRMED

A Reservation has been successfully created and is waiting for activation.

The Connector is reserved.

No Charging Session exists.

---

## ACTIVE

The Reservation has been activated by a valid Charging Session.

The Connector is in use.

---

## COMPLETED

The associated Charging Session has ended successfully.

The Reservation lifecycle is finished.

---

## CANCELLED

The Reservation was cancelled before the normal cancellation deadline.

No penalty or warning is associated with this outcome.

---

## LATE_CANCELLED

The Reservation was cancelled after the cancellation deadline but before charging actually started.

The Connector is immediately released.

Historical information is preserved for future operational analysis.

---

## NO_SHOW

The Reservation was never activated before the Grace Period expired.

The Connector becomes available again.

Historical information is preserved.

---

# 12. Reservation Timeline

Example reservation:

```text
Reservation

Start: 10:00

End:   11:00
```

Timeline:

```text
09:45
│
│ Early Start Window Opens
│
10:00
│
│ Official Reservation Start
│
10:15
│
│ Grace Period Ends
│
11:00
│
│ Reservation Ends
```

If no Charging Session starts before the Grace Period expires:

```text
Reservation

↓

NO_SHOW
```

If charging starts during the valid activation window:

```text
CONFIRMED

↓

ACTIVE
```

---

# 13. Business Rules

## BR-001 — Connector Exclusivity

Two Reservations shall never overlap on the same Connector.

For any Reservation:

```
existing.connector_id == new.connector_id
```

the following intervals are invalid:

```text
09:00 ─────────────── 10:30

09:45 ─────────────── 11:00
```

---

## BR-002 — Vehicle Exclusivity

A Vehicle shall not own overlapping Reservations.

The same authenticated identity may own multiple Vehicles.

Different Vehicles may reserve different Connectors simultaneously.

Example:

```text
Owner

├── Vehicle A
│     Reservation
│
└── Vehicle B
      Reservation
```

This is valid.

---

## BR-003 — Reservation Duration

Reservations shall satisfy:

Minimum duration:

```text
15 minutes
```

Maximum duration:

```text
24 hours
```

Reservations outside these limits shall be rejected.

---

## BR-004 — Back-to-Back Reservations

Back-to-Back Reservations are valid.

Example:

```text
09:00 ───── 10:00

10:00 ───── 11:00
```

The API may include an informational warning indicating that the previous user could still be disconnecting.

This warning shall not prevent Reservation creation.

---

## BR-005 — Early Start

Charging may begin before the official reservation start.

Early Start is permitted only when:

- the Early Start window has opened;
- the Connector is available;
- no Charging Session is active;
- the Reservation is still CONFIRMED.

The default Early Start window is:

```text
15 minutes
```

Early Start shall never modify the Reservation end time.

---

## BR-006 — Grace Period

The Grace Period begins at the scheduled reservation start.

The default Grace Period is:

```text
15 minutes
```

Charging Sessions created during the Grace Period activate the Reservation normally.

After the Grace Period expires:

```text
CONFIRMED

↓

NO_SHOW
```

---

## BR-007 — Reservation Activation

A Reservation may become ACTIVE only when:

- its status is CONFIRMED;
- the Reservation Owner starts a valid Charging Session;
- the Charging Session references the reserved Connector;
- the Charging Session references the reserved Vehicle;
- the activation occurs within the valid activation window.

No other operation may activate a Reservation.

---

## BR-008 — Reservation Completion

A Reservation becomes COMPLETED only when its Charging Session finishes.

Completion is triggered by the Charging Session lifecycle.

Reservations cannot be completed directly through the Reservation API.

---

## BR-009 — Normal Cancellation

Reservations may be cancelled freely until:

```text
60 minutes before start_at
```

The resulting status is:

```text
CANCELLED
```

The Connector becomes immediately available.

---

## BR-010 — Late Cancellation

Reservations may still be cancelled after the normal cancellation deadline provided that:

- the Reservation has not been activated;
- the Reservation is still CONFIRMED.

The resulting status is:

```text
LATE_CANCELLED
```

Late Cancellation shall:

- immediately release the Connector;
- preserve historical information;
- record the late cancellation timestamp.

Future specifications may associate penalties or operational policies with Late Cancellation.

No penalty behavior is defined by this specification.

---

## BR-011 — No-Show Detection

If no valid Charging Session starts before:

```text
start_at + grace_period
```

the Reservation becomes:

```text
NO_SHOW
```

The Connector is immediately released.

---

## BR-012 — Fixed Reservation Window

Reservation end time is immutable.

Neither:

- Early Start;
- Charging Session duration;
- Connector availability;

may automatically extend a Reservation.

Charging Sessions shall respect the Reservation end time.

Future Reservation extension capabilities are outside the scope of this specification.

---

## BR-013 — Historical Preservation

Completed Reservations shall never be physically removed as part of normal application behavior.

Historical Reservation information is required for:

- analytics;
- Digital Twin simulations;
- utilization reports;
- no-show analysis;
- future scheduling optimization.

Deletion behavior, if ever required, shall be defined by a dedicated specification.

# 14. Authorization Matrix

Authorization is defined by SPEC-005.

This specification extends the authorization model with Reservation-specific permissions.

Reservations always belong to the authenticated Reservation Owner.

Administrative permissions remain governed by Identity and Access.

---

## Platform Administrator

Platform Administrators may:

- create Reservations;
- view any Reservation;
- cancel any Reservation;
- inspect Reservation history;
- perform administrative Reservation operations.

---

## Facility Operator

Facility Operators may:

- view Reservations belonging to their managed Facilities;
- inspect Reservation history for operational purposes.

Facility Operators shall not:

- create Reservations on behalf of users;
- activate Reservations;
- cancel Reservations unless future operational policies explicitly allow it.

---

## Human Account

Human accounts may:

- create Reservations;
- view their own Reservations;
- cancel their own Reservations;
- activate Reservations indirectly through Charging Sessions.

Human accounts shall not access Reservations belonging to other users.

---

## Technical Client

Technical Clients participate in the reservation workflow exactly like Human accounts.

Technical Clients may:

- create Reservations;
- view their own Reservations;
- cancel their own Reservations;
- activate Reservations through Charging Sessions.

Technical Clients are intended to support:

- Digital Twin simulations;
- automated testing;
- fleet simulations;
- synthetic charging workloads.

Technical Clients shall not perform infrastructure administration.

---

## Researcher

Researchers have read-only access.

Researchers may inspect Reservation information for analysis purposes.

Researchers shall not modify Reservations.

---

## Data Scientist

Data Scientists have read-only access.

Reservations may be consumed for experimentation and analytics.

Modification operations are prohibited.

---

# 15. API

The Reservation capability exposes the following REST endpoints.

---

## Create Reservation

```http
POST /reservations
```

Creates a new Reservation.

Possible responses:

```
201 Created
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Validation Error
```

---

## List Reservations

```http
GET /reservations
```

Returns Reservations visible to the authenticated identity.

Filtering may include:

- owner
- vehicle
- connector
- status
- Facility
- Charging Station
- time interval

Pagination is implementation-defined.

---

## Get Reservation

```http
GET /reservations/{reservationId}
```

Returns Reservation details.

---

## Update Reservation

```http
PATCH /reservations/{reservationId}
```

Allows modification of mutable Reservation attributes.

Allowed modifications are limited to:

- reservation start
- reservation end
- associated Vehicle

provided that all validation rules remain satisfied.

Immutable attributes include:

- id
- owner_id
- connector_id
- created_at

---

## Cancel Reservation

```http
POST /reservations/{reservationId}/cancel
```

Cancellation follows the business rules defined in BR-009 and BR-010.

The resulting status is automatically determined by the domain.

Clients shall not choose:

```
CANCELLED

or

LATE_CANCELLED
```

---

## Connector Reservation Calendar

```http
GET /connectors/{connectorId}/reservations
```

Returns Reservations for one Connector.

Implementations may support filtering by:

- date
- interval
- status

---

# 16. API Warnings

Reservation creation may return informational warnings.

Warnings do not prevent Reservation creation.

Example:

```json
{
  "reservation": {
    "id": "...",
    "status": "CONFIRMED"
  },
  "warnings": [
    {
      "code": "BACK_TO_BACK_RESERVATION",
      "message": "Another reservation ends immediately before this reservation."
    }
  ]
}
```

Supported warning codes include:

```
BACK_TO_BACK_RESERVATION

EARLY_START_AVAILABLE

LATE_CANCELLATION

NO_SHOW_WARNING

RESERVATION_ENDING_SOON
```

Warnings are not persisted as Reservation state.

---

# 17. Validation Rules

## VR-001

Connector shall exist.

---

## VR-002

Vehicle shall exist.

---

## VR-003

Reservation Owner shall own the selected Vehicle.

---

## VR-004

Reservation interval shall satisfy:

```
15 minutes

≤ duration ≤

24 hours
```

---

## VR-005

Connector shall not contain overlapping Reservations.

---

## VR-006

Vehicle shall not contain overlapping Reservations.

---

## VR-007

Reservation start shall occur before Reservation end.

---

## VR-008

Reservation shall not be created in the past.

---

## VR-009

Only CONFIRMED Reservations may be cancelled.

---

## VR-010

ACTIVE Reservations cannot be cancelled.

Charging Session lifecycle controls Reservation completion.

---

## VR-011

COMPLETED Reservations are immutable.

---

## VR-012

NO_SHOW Reservations are immutable.

---

## VR-013

LATE_CANCELLED Reservations are immutable.

---

## VR-014

Reservation activation is allowed only inside the valid activation window.

---

## VR-015

Charging Session shall reference:

- the reserved Connector;
- the reserved Vehicle;
- the Reservation Owner.

---

# 18. Persistence Model

The Reservation Aggregate introduces the following persistence model.

```
reservations

id (UUID)

owner_id

vehicle_id

connector_id

start_at

end_at

status

created_at

updated_at

activated_at

completed_at

cancelled_at

late_cancelled_at

no_show_at
```

---

## Constraints

Database constraints shall enforce:

- valid Reservation status;
- start_at < end_at;
- duration ≥ 15 minutes;
- duration ≤ 24 hours.

Connector overlap and Vehicle overlap shall be enforced through application validation and transactional consistency.

---

# 19. OpenAPI Requirements

The generated OpenAPI documentation shall expose:

- Reservation schemas;
- Reservation status enumeration;
- warning schemas;
- authentication requirements;
- authorization requirements.

Bearer authentication shall follow SPEC-005.

Sensitive internal fields shall never appear in public schemas.

Examples shall be provided for:

- Reservation creation;
- successful cancellation;
- late cancellation;
- validation conflict;
- Connector overlap.

# 20. Acceptance Criteria

The Reservation capability is considered complete only when all of the following conditions are satisfied.

## Domain

- [ ] Reservation Aggregate implemented.
- [ ] Reservation lifecycle implemented.
- [ ] Reservation state transitions enforce this specification.
- [ ] Reservation invariants are preserved.
- [ ] Reservation history is preserved.

---

## Reservation Creation

- [ ] Reservations can be created only by authenticated identities.
- [ ] Human accounts may create Reservations.
- [ ] Technical Clients may create Reservations.
- [ ] Connector existence is validated.
- [ ] Vehicle existence is validated.
- [ ] Vehicle ownership is validated.
- [ ] Reservation duration is validated.
- [ ] Reservation cannot start in the past.
- [ ] Connector overlap is rejected.
- [ ] Vehicle overlap is rejected.

---

## Reservation Lifecycle

- [ ] Reservation starts in CONFIRMED.
- [ ] Charging Session activates Reservation.
- [ ] Charging Session completes Reservation.
- [ ] Grace Period correctly detects NO_SHOW.
- [ ] Early Start follows the defined rules.
- [ ] Reservation end time remains fixed.
- [ ] ACTIVE Reservations cannot be cancelled.
- [ ] COMPLETED Reservations cannot be modified.

---

## Cancellation

- [ ] Cancellation before the cutoff produces CANCELLED.
- [ ] Cancellation after the cutoff produces LATE_CANCELLED.
- [ ] Late Cancellation immediately releases the Connector.
- [ ] Cancellation timestamps are preserved.

---

## Authorization

- [ ] Platform Administrators may manage all Reservations.
- [ ] Human users may manage only their own Reservations.
- [ ] Technical Clients may manage only their own Reservations.
- [ ] Facility Operators may inspect Reservations within their managed Facilities.
- [ ] Read-only roles cannot modify Reservations.

---

## API

- [ ] REST endpoints implemented.
- [ ] OpenAPI documentation generated.
- [ ] Bearer authentication applied.
- [ ] Validation responses documented.
- [ ] Warning responses documented.

---

## Persistence

- [ ] Reservation persistence implemented.
- [ ] Database constraints implemented.
- [ ] Status validation implemented.
- [ ] Duration validation implemented.

---

## Testing

Automated tests shall include at minimum:

### Domain

- Reservation creation.
- Reservation overlap.
- Vehicle overlap.
- Duration validation.
- Early Start.
- Grace Period.
- No-Show.
- Normal Cancellation.
- Late Cancellation.
- Reservation completion.

### Persistence

- Repository CRUD.
- Status persistence.
- Constraint validation.

### API

- Reservation creation.
- Reservation retrieval.
- Reservation listing.
- Reservation cancellation.
- Validation failures.
- Authentication.
- Authorization.

### Integration

- Reservation creation followed by Charging Session activation.
- Reservation completion after Charging Session completion.
- Back-to-Back Reservation.
- Concurrent Reservation conflict.
- Technical Client Reservation workflow.

---

# 21. Future Integration

The Reservation capability prepares the foundation for the following specifications.

---

## SPEC-007 — Charging Sessions

Charging Sessions activate Reservations.

Expected integration:

```text
Reservation

CONFIRMED

↓

Charging Session Starts

↓

ACTIVE

↓

Charging Session Ends

↓

COMPLETED
```

Reservation lifecycle remains owned by the Reservation Aggregate.

Charging Sessions shall request state transitions rather than modifying persistence directly.

---

## SPEC-008 — Telemetry

Telemetry will provide operational events associated with Reservations, including:

- reservation activation;
- reservation completion;
- charging duration;
- connector occupancy;
- no-show statistics.

Telemetry implementation is intentionally outside the scope of this specification.

---

## SPEC-009 — Domain Events

Future Domain Events may include:

```text
ReservationCreated

ReservationActivated

ReservationCompleted

ReservationCancelled

ReservationLateCancelled

ReservationNoShow
```

This specification defines the business events conceptually only.

No messaging infrastructure is required.

---

## SPEC-010 — Analytics

Reservation history may later support:

- occupancy reports;
- utilization reports;
- no-show rates;
- cancellation rates;
- reservation lead time;
- connector demand;
- infrastructure planning.

---

# 22. Implementation Notes

The implementation shall follow the architectural principles established by the project.

Reservation business rules belong to the Domain layer.

Application Services coordinate Reservation use cases.

Infrastructure owns:

- persistence;
- repository implementations;
- database migrations.

The API layer shall:

- expose REST endpoints;
- validate request DTOs;
- map domain responses to HTTP responses;
- expose warnings without embedding business logic.

Reservation state transitions shall never be implemented directly inside controllers.

---

# 23. Non-Functional Requirements

The Reservation capability shall:

- remain deterministic;
- support concurrent reservation requests safely;
- preserve transactional consistency;
- avoid partial state transitions;
- expose OpenAPI documentation;
- support automated testing;
- integrate with the project observability stack.

Reservation creation shall be atomic.

Concurrent requests for the same Connector shall never result in two overlapping Reservations.

---

# 24. Design Rationale

Several design decisions intentionally prioritize long-term maintainability.

Reservations are created for Connectors rather than Charging Stations because charging ultimately occurs through a specific physical connector.

Reservations belong to Vehicles rather than directly to users, allowing one authenticated identity to manage multiple vehicles while preventing conflicting reservations for the same vehicle.

Late Cancellation is modeled separately from No-Show because the operational consequences differ.

A user who informs the platform that charging will not occur should immediately release the Connector while still preserving historical information.

The Reservation end time remains immutable to guarantee predictable infrastructure scheduling and avoid cascading conflicts.

Warnings are represented as API responses rather than Reservation state to avoid polluting the domain model with transient operational information.

---

# 25. Summary

This specification introduces the Reservation capability as the scheduling foundation of SCEP.

It establishes:

- the Reservation Aggregate;
- Reservation lifecycle;
- scheduling invariants;
- cancellation policies;
- no-show detection;
- authorization model;
- REST API;
- persistence model;
- validation rules;
- implementation guidance.

Together with Facilities, Charging Stations and Identity, Reservations complete the operational planning layer of the platform and provide the necessary foundation for Charging Sessions, Telemetry and Analytics.