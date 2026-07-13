# SPEC-006 — Reservations

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

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

# 1. Purpose

This specification defines the Reservation capability of the Smart Charging Experimentation
Platform (SCEP) and introduces the minimum Vehicle capability required to schedule connector
usage.

A Reservation grants one Authenticated Identity the exclusive right to use one specific
Connector with one owned Vehicle during a scheduled time interval. A Reservation does not
start charging. It exposes domain operations that a future Charging Session may use to activate
and complete the Reservation.

---

# 2. Goals

This specification shall:

- define the Reservation Aggregate and its lifecycle;
- define the minimum Vehicle entity and ownership model;
- allow Human and Technical Client identities to manage owned Vehicles and Reservations;
- prevent overlapping Reservations for the same Connector or Vehicle;
- define deterministic cancellation, Early Start and No-Show behavior;
- preserve historical Vehicle and Reservation records;
- define REST contracts, persistence requirements and authorization rules;
- prepare domain operations for Charging Sessions without requiring SPEC-007 implementation.

---

# 3. Scope

This specification defines:

- Vehicle creation, retrieval, listing and update;
- Vehicle ownership and lifecycle;
- Reservation creation, retrieval, listing, rescheduling and cancellation;
- Connector and Vehicle calendar blocking;
- Reservation lifecycle transitions;
- temporal and overlap validation;
- automatic No-Show reconciliation;
- authorization and visibility;
- REST API contracts and status codes;
- persistence and concurrency requirements;
- OpenAPI, testing and acceptance requirements.

---

# 4. Out of Scope

The following capabilities are excluded:

- Charging Session endpoints or execution;
- API-to-API integration with Charging Sessions;
- energy interruption or electrical control;
- battery, manufacturer, model or charging-power attributes for Vehicles;
- connector compatibility and simulation-specific Vehicle attributes;
- Vehicle deletion;
- recurring Reservations, waiting lists or automatic extensions;
- penalties, billing, pricing or payments;
- email, push, SMS or lifecycle notification delivery;
- telemetry ingestion, analytics or Domain Event implementation;
- OCPP and charger communication protocols.

---

# 5. Ubiquitous Language

## Reservation

A scheduled exclusive allocation of one specific Connector to one owned Vehicle during a
half-open time interval.

## Reservation Owner

The Authenticated Identity responsible for a Reservation. The owner may be a Human or Technical
Client account.

## Vehicle

A physical or simulated electric vehicle owned by one Authenticated Identity. SPEC-006 models
only the information required for reservation scheduling and historical association.

## Connector Calendar

The set of CONFIRMED and ACTIVE Reservations that block a Connector during their scheduled
intervals.

## Vehicle Calendar

The set of CONFIRMED and ACTIVE Reservations that block a Vehicle during their scheduled
intervals.

## Early Start

The ability to activate a CONFIRMED Reservation during the 15 minutes before `start_at`, subject
to infrastructure and Charging Session invariants.

## Grace Period

The 15-minute interval after `start_at` during which a CONFIRMED Reservation may still be
activated.

## No-Show

A CONFIRMED Reservation that was not activated before its Grace Period expired.

## Late Cancellation

A cancellation requested after the normal cancellation cutoff but before activation.

## Back-to-Back Reservations

Reservations whose half-open intervals meet at one boundary without overlapping, such as
09:00–10:00 and 10:00–11:00.

---

# 6. Domain Model

```text
Identity
    ├── owns ───────────► Vehicle
    └── creates ────────► Reservation
                              │
                              ├── assigned to ───► Vehicle
                              └── reserves ──────► Connector
                                                       │
                                                       └── belongs to
                                                           Charging Station
                                                               │
                                                               └── belongs to Facility
```

Reservation is the Aggregate Root of the Reservation Aggregate. Vehicle is a supporting domain
entity introduced by this specification. Connector, Charging Station, Facility and Identity are
external domain concepts referenced by identifier.

Vehicle remains inside the Smart Charging domain and does not introduce a new bounded context,
module, service or deployable container.

---

# 7. Vehicle Model

The minimum Vehicle model is:

```text
Vehicle

id
owner_id
display_name
status
created_at
updated_at
```

Supported statuses are:

```text
ACTIVE
INACTIVE
```

## Vehicle Rules

- A Vehicle shall belong to exactly one Authenticated Identity.
- Human and Technical Client identities may own multiple Vehicles.
- Only the owner may manage a Vehicle unless a Platform Administrator is acting.
- Only ACTIVE Vehicles may receive new Reservations or be selected during rescheduling.
- INACTIVE Vehicles shall remain visible in historical Reservation records.
- Vehicle ownership shall be immutable.
- Physical deletion is not required and shall not be exposed by this specification.
- `display_name` shall be required and non-empty after trimming.
- Advanced physical, electrical and simulation attributes are deferred.

Deactivating a Vehicle shall prevent new Reservations and rescheduling to that Vehicle. It shall
not rewrite history or automatically cancel existing Reservations. Existing blocking Reservations
remain subject to their normal lifecycle and may be cancelled explicitly.

---

# 8. Reservation Aggregate

The Reservation Aggregate contains:

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

The Aggregate owns:

- lifecycle transitions;
- cancellation classification;
- activation-window validation;
- rescheduling eligibility;
- historical timestamps.

Application services coordinate external existence, ownership, infrastructure eligibility,
calendar overlap and atomic persistence checks.

The invariant below shall always hold:

```text
reservation.owner_id == vehicle.owner_id
```

The Connector is immutable after Reservation creation. A different Connector requires a new
Reservation after the existing Reservation is cancelled when eligible.

---

# 9. Reservation Lifecycle

Supported statuses are:

```text
CONFIRMED
ACTIVE
COMPLETED
CANCELLED
LATE_CANCELLED
NO_SHOW
```

Valid transitions are:

```text
CONFIRMED → ACTIVE
CONFIRMED → CANCELLED
CONFIRMED → LATE_CANCELLED
CONFIRMED → NO_SHOW
ACTIVE → COMPLETED
```

No other transition is allowed.

## CONFIRMED

The Reservation was accepted and blocks its Connector and Vehicle calendars.

## ACTIVE

A valid Charging Session activated the Reservation. It continues to block both calendars.

## COMPLETED

The future Charging Session completed. The Reservation is terminal and historical.

## CANCELLED

The Reservation was cancelled no later than 60 minutes before `start_at`. It is terminal and
releases both calendars immediately.

## LATE_CANCELLED

The Reservation was cancelled after the normal cutoff but before activation. It is terminal,
releases both calendars immediately and remains distinguishable from NO_SHOW.

## NO_SHOW

The Reservation was not activated before the Grace Period expired. It is terminal and releases
both calendars.

ACTIVE and terminal Reservations are immutable through the Reservation API.

---

# 10. Time and Interval Semantics

All Reservation intervals shall use half-open semantics:

```text
[start_at, end_at)
```

Two intervals overlap only when:

```text
existing.start_at < new.end_at
and
new.start_at < existing.end_at
```

Therefore, the following Reservations are valid and back-to-back:

```text
09:00–10:00
10:00–11:00
```

Temporal requirements are:

- persisted timestamps shall be timezone-aware UTC values;
- API timestamps shall use ISO 8601 and include an explicit timezone offset;
- application comparisons shall use one consistent application clock;
- timestamps received through the API shall be normalized to UTC before comparison;
- `start_at` shall be earlier than `end_at`;
- new Reservations shall not start in the past relative to the application clock;
- the minimum duration of 15 minutes is inclusive;
- the maximum duration of 24 hours is inclusive;
- no local server timezone shall be assumed.

The 24-hour maximum is an upper validation boundary supporting slow, overnight and experimental
charging scenarios. It is not the expected duration of every Charging Session.

Facility timezone remains relevant for display and business interpretation, while persistence and
comparison use UTC consistently.

---

# 11. Calendar Blocking and Overlap

Only CONFIRMED and ACTIVE Reservations block Connector and Vehicle calendars.

The following historical statuses do not block future Reservations:

```text
COMPLETED
CANCELLED
LATE_CANCELLED
NO_SHOW
```

Creation and rescheduling shall reject an overlap when any blocking Reservation intersects the
proposed interval for:

- the same Connector; or
- the same Vehicle.

One identity may hold overlapping Reservations only when they use different Vehicles and
different Connectors. Different Vehicles cannot reserve the same Connector for overlapping
intervals, and one Vehicle cannot reserve different Connectors for overlapping intervals.

Calendar availability queries and persistence conflict checks shall ignore terminal statuses.
Cancellation and No-Show transitions shall release both calendars immediately without deleting
the historical Reservation.

---

# 12. Business Rules

## BR-001 — Reservation Target

A Reservation shall reference exactly one Connector. It shall not target a Facility, Charging
Station or generic connector type.

## BR-002 — Vehicle Ownership

The selected Vehicle shall exist, be ACTIVE and belong to the Reservation Owner.

## BR-003 — Connector Eligibility

A new or rescheduled Reservation requires a Connector that:

- exists;
- is operationally eligible for future reservation under SPEC-004;
- belongs to a Charging Station with `Active` status;
- belongs to a Facility with `Active` status;
- is not blocked by another CONFIRMED or ACTIVE Reservation during the proposed interval.

An `OutOfService` Connector is not eligible. A current `Reserved` or `Charging` state does not by
itself invalidate a non-overlapping future interval; actual interval eligibility is determined by
the Connector calendar. No new Connector state is introduced by this specification.

## BR-004 — Duration

Reservation duration shall be at least 15 minutes and at most 24 hours, inclusive.

## BR-005 — Connector Exclusivity

Blocking Reservations for the same Connector shall not overlap.

## BR-006 — Vehicle Exclusivity

Blocking Reservations for the same Vehicle shall not overlap.

## BR-007 — Back-to-Back Reservations

Back-to-back Reservations shall be accepted. The synchronous response may contain a
`BACK_TO_BACK_RESERVATION` warning.

## BR-008 — Early Start

The default Early Start window opens 15 minutes before `start_at`. Activation is allowed only
when:

- the Reservation is CONFIRMED;
- the activation window has opened;
- the Connector is operational and available;
- no Charging Session is active on the Connector;
- the Charging Session references the Reservation Owner, Vehicle and Connector.

Early Start shall not automatically extend `end_at`.

## BR-009 — Grace Period and Activation Window

The default Grace Period ends 15 minutes after `start_at`. Activation is allowed while:

```text
start_at - 15 minutes <= now <= start_at + 15 minutes
```

## BR-010 — No-Show

A CONFIRMED Reservation shall become NO_SHOW when:

```text
now > start_at + 15 minutes
```

and no valid Charging Session has activated it.

The application shall reconcile overdue Reservations automatically and deterministically.
Implementation may use scheduled processing, background processing or opportunistic overdue-state
reconciliation, provided externally observable state is consistent and does not require manual
user action.

## BR-011 — Cancellation

Cancellation is allowed only for a CONFIRMED, non-activated Reservation.

The application shall reconcile an overdue CONFIRMED Reservation against BR-010 before applying
the cancellation command. A Reservation already due for NO_SHOW shall not be reclassified as a
Late Cancellation merely because reconciliation had not yet run.

When:

```text
now <= start_at - 60 minutes
```

the result shall be CANCELLED. When:

```text
now > start_at - 60 minutes
```

the result shall be LATE_CANCELLED. Late cancellation shall always remain available before
activation, release both calendars immediately and preserve history. No penalty is defined.

## BR-012 — No Automatic Extension

Early Start, Charging Session duration and later Connector availability shall never automatically
extend `end_at`. Explicit rescheduling is a deliberate operation and is not an automatic
extension.

## BR-013 — Explicit Rescheduling

An owned CONFIRMED Reservation may be rescheduled by changing `start_at`, `end_at` or `vehicle_id`.
Rescheduling shall:

- occur before the Early Start window opens;
- revalidate Vehicle ownership and ACTIVE status;
- revalidate Connector, Charging Station and Facility eligibility;
- revalidate duration, temporal ordering and past-time rules;
- revalidate Connector and Vehicle overlaps atomically;
- preserve `owner_id`, `connector_id`, `id` and `created_at`.

ACTIVE and terminal Reservations shall not be rescheduled.

## BR-014 — Activation and Completion Domain Operations

Reservation shall expose domain operations for future activation and completion. Activation shall
enforce BR-008 and BR-009. Completion shall be allowed only from ACTIVE and shall record
`completed_at`.

HTTP integration with Charging Sessions is deferred to SPEC-007.

## BR-015 — Historical Preservation

Vehicles and Reservations referenced by operational history shall not be physically removed by
normal application behavior.

---

# 13. Authorization and Visibility

Authorization shall evaluate account type, Human Role and resource ownership separately.

## Platform Administrator

May manage all Vehicles and Reservations, including creation, retrieval, rescheduling and
cancellation subject to the same domain rules. Administrative action does not bypass temporal,
overlap or lifecycle invariants.

## Facility Operator

May view Reservations whose Connector belongs to a managed Facility. A Facility Operator shall
not create, reschedule or cancel Reservations on behalf of owners unless a future policy explicitly
adds that capability.

## Human Account

An authenticated Human account may:

- manage owned Vehicles;
- create Reservations for owned ACTIVE Vehicles;
- view owned Reservations;
- reschedule eligible owned Reservations;
- cancel owned CONFIRMED Reservations.

These owned workflows do not require the `EVDriver` Role; ownership grants the capability unless
another project-wide access rule explicitly restricts it.

## Technical Client

A Technical Client may perform the same owned Vehicle and Reservation workflow required for
simulation. It shall not administer identities or charging infrastructure.

## Researcher and Data Scientist

Human accounts with Researcher or Data Scientist Roles retain read-only visibility according to
SPEC-005 and future analytical visibility policies. They shall not gain modification rights from
those Roles. They may still perform their own ownership-based workflow when acting on resources
they own.

Unauthorized resource access shall use `404 Not Found` when resource existence is concealed in
accordance with SPEC-005. Explicitly forbidden, non-concealed capabilities shall use `403
Forbidden`.

---

# 14. Vehicle API Contract

All Vehicle endpoints require authentication.

## 14.1 Create Vehicle

```http
POST /vehicles
```

Request:

```json
{
  "display_name": "Primary EV"
}
```

The owner is derived from the Authenticated Identity. A Platform Administrator acting for another
owner may supply `owner_id` through an explicitly documented administrative request field.

Response: `201 Created` with a Vehicle response.

## 14.2 List Vehicles

```http
GET /vehicles
```

Owners receive their own Vehicles. Platform Administrators may filter by `owner_id`. Other roles
shall not use this endpoint to enumerate Vehicles belonging to other identities.

Response: `200 OK` with a list of Vehicle responses.

## 14.3 Get Vehicle

```http
GET /vehicles/{vehicleId}
```

Returns an owned or administratively visible Vehicle. Non-visible Vehicles return `404 Not Found`.

## 14.4 Update Vehicle

```http
PATCH /vehicles/{vehicleId}
```

Mutable fields:

- `display_name`;
- `status`.

Request:

```json
{
  "display_name": "Primary EV Updated",
  "status": "INACTIVE"
}
```

At least one field shall be supplied. Ownership and owner identifier are immutable.

## Vehicle Response

```json
{
  "id": "vehicle-id",
  "owner_id": "identity-id",
  "display_name": "Primary EV",
  "status": "ACTIVE",
  "created_at": "2026-07-12T12:00:00Z",
  "updated_at": "2026-07-12T12:00:00Z"
}
```

Common responses are `401 Unauthorized`, `403 Forbidden`, `404 Not Found` and `422
Unprocessable Entity`.

---

# 15. Reservation API Contract

All Reservation endpoints require authentication.

## 15.1 Create Reservation

```http
POST /reservations
```

Request:

```json
{
  "vehicle_id": "vehicle-id",
  "connector_id": "connector-id",
  "start_at": "2026-07-13T09:00:00-03:00",
  "end_at": "2026-07-13T10:00:00-03:00"
}
```

The owner is derived from the Authenticated Identity unless a Platform Administrator uses an
explicitly documented `owner_id` administrative field. Success returns `201 Created` with the
response envelope defined in Section 16.

## 15.2 List Reservations

```http
GET /reservations
```

Supported filters shall include:

- `owner_id` where authorized;
- `vehicle_id`;
- `connector_id`;
- `status`;
- `facility_id`;
- `station_id`;
- interval boundaries;
- pagination.

Owners receive owned Reservations. Platform Administrators may view all. Facility Operators may
view Reservations for managed Facilities. Researcher and Data Scientist visibility remains
read-only and shall follow authorized visibility rules.

## 15.3 Get Reservation

```http
GET /reservations/{reservationId}
```

Returns a visible Reservation or `404 Not Found` when absent or concealed.

## 15.4 Reschedule Reservation

```http
PATCH /reservations/{reservationId}
```

Request may contain one or more mutable fields:

```json
{
  "vehicle_id": "another-owned-active-vehicle-id",
  "start_at": "2026-07-13T10:00:00-03:00",
  "end_at": "2026-07-13T11:00:00-03:00"
}
```

All creation validations shall be reapplied. `connector_id` shall not be accepted. Success returns
`200 OK`.

## 15.5 Cancel Reservation

```http
POST /reservations/{reservationId}/cancel
```

The domain determines CANCELLED or LATE_CANCELLED. Clients shall not choose the result. Success
returns `200 OK` with the updated Reservation and a `LATE_CANCELLATION` warning when applicable.

## 15.6 Connector Reservation Calendar

```http
GET /connectors/{connectorId}/reservations
```

Returns visible Reservations for one Connector and supports interval and status filters. Calendar
availability calculations shall treat only CONFIRMED and ACTIVE as blocking.

## Reservation Response

```json
{
  "id": "reservation-id",
  "owner_id": "identity-id",
  "vehicle_id": "vehicle-id",
  "connector_id": "connector-id",
  "start_at": "2026-07-13T12:00:00Z",
  "end_at": "2026-07-13T13:00:00Z",
  "status": "CONFIRMED",
  "created_at": "2026-07-12T12:00:00Z",
  "updated_at": "2026-07-12T12:00:00Z",
  "activated_at": null,
  "completed_at": null,
  "cancelled_at": null,
  "late_cancelled_at": null,
  "no_show_at": null
}
```

---

# 16. API Warnings and Future Notifications

Synchronous response warnings are informational and shall not become Reservation status.

```json
{
  "reservation": {
    "id": "reservation-id",
    "status": "CONFIRMED"
  },
  "warnings": [
    {
      "code": "BACK_TO_BACK_RESERVATION",
      "message": "Another reservation ends when this reservation begins."
    }
  ]
}
```

Supported synchronous warning codes are:

```text
BACK_TO_BACK_RESERVATION
LATE_CANCELLATION
```

Future lifecycle notification concepts include:

```text
EARLY_START_AVAILABLE
NO_SHOW_DEADLINE_APPROACHING
RESERVATION_ENDING_SOON
```

These lifecycle concepts are not returned automatically during Reservation creation. Notification
delivery by email, push or SMS remains out of scope.

---

# 17. Status Codes and Error Semantics

Equivalent Vehicle and Reservation endpoints shall apply these conventions consistently:

- `200 OK`: successful retrieval, update, rescheduling or cancellation;
- `201 Created`: successful Vehicle or Reservation creation;
- `401 Unauthorized`: missing or invalid authentication;
- `403 Forbidden`: known identity explicitly lacks a non-concealed capability;
- `404 Not Found`: resource does not exist or is concealed from the actor;
- `409 Conflict`: Connector or Vehicle scheduling overlap, or another state conflict;
- `422 Unprocessable Entity`: invalid payload, duration, temporal ordering, timestamp offset,
  inactive Vehicle, ineligible infrastructure or invalid lifecycle request.

Scheduling conflicts shall include a stable machine-readable code identifying Connector or Vehicle
overlap without exposing another owner's private Reservation data.

---

# 18. Persistence Model

## vehicles

```text
id (UUID)
owner_id
display_name
status
created_at
updated_at
```

Constraints shall include:

- primary key on `id`;
- foreign key from `owner_id` to the Identity/User owner;
- valid ACTIVE or INACTIVE status;
- non-empty display name;
- immutable owner relationship;
- indexes supporting owner listing and status filtering.

## reservations

```text
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

Constraints shall include:

- primary key on `id`;
- foreign keys to owner, Vehicle and Connector;
- `reservations.vehicle_id` referencing `vehicles.id`;
- valid Reservation status;
- `start_at < end_at`;
- inclusive duration boundaries from 15 minutes through 24 hours;
- timezone-aware UTC persistence;
- historical references that are not removed by Vehicle inactivation;
- indexes supporting owner, Vehicle, Connector, status and interval queries.

The implementation shall preserve:

```text
reservation.owner_id == vehicle.owner_id
```

Application and persistence queries shall treat only CONFIRMED and ACTIVE as calendar-blocking.
Terminal statuses shall remain queryable history and shall not cause overlap rejection.

---

# 19. Concurrency and Transactional Consistency

Reservation creation and rescheduling shall be atomic.

Concurrent requests shall not create overlapping blocking Reservations for:

- the same Connector;
- the same Vehicle.

The implementation may use transactional locking, exclusion constraints or another safe strategy.
No specific locking mechanism is mandated, but checking outside a transaction without equivalent
conflict protection is insufficient.

Lifecycle transitions shall avoid partial updates. Calendar release and status/timestamp changes
shall become visible atomically.

---

# 20. OpenAPI Requirements

OpenAPI shall document:

- Vehicle and Reservation request and response schemas;
- Vehicle and Reservation status enumerations;
- warning and scheduling-conflict schemas;
- bearer authentication;
- mutable and immutable fields;
- ISO 8601 timestamp examples with explicit offsets;
- all status codes defined in Section 17;
- visibility and ownership requirements without exposing sensitive fields.

No Vehicle or Reservation endpoint in this specification shall use DELETE.

---

# 21. Testing Requirements

Tests are required but are not implemented by this documentation change.

## Vehicle Domain and Persistence

- creation and non-empty display name;
- Human and Technical Client ownership;
- multiple Vehicles per identity;
- ACTIVE and INACTIVE transitions;
- immutable ownership;
- historical Reservation association after inactivation;
- repository persistence, owner listing and status filtering.

## Vehicle API

- create, list, retrieve and patch owned Vehicles;
- Platform Administrator management;
- concealed non-owned Vehicle access;
- inactive Vehicle rejection during Reservation creation and rescheduling.

## Reservation Domain

- every valid and invalid state transition;
- minimum and maximum inclusive durations;
- half-open overlap semantics;
- Connector and Vehicle overlap;
- valid back-to-back Reservations;
- normal and late cancellation boundaries;
- immediate calendar release;
- Early Start and Grace Period boundaries;
- deterministic No-Show processing;
- no automatic extension;
- explicit rescheduling before the Early Start window;
- immutable ACTIVE and terminal Reservations.

## Persistence and Concurrency

- UTC timestamp persistence and offset normalization;
- owner/Vehicle invariant;
- valid status constraints;
- terminal statuses excluded from blocking queries;
- concurrent conflict requests for the same Connector;
- concurrent conflict requests for the same Vehicle;
- atomic creation, rescheduling and lifecycle transitions.

## Authorization and API

- Human owned workflow;
- Technical Client owned Vehicle and Reservation workflow;
- Platform Administrator access;
- Facility Operator managed-Facility visibility without mutation;
- Researcher and Data Scientist read-only behavior;
- `401`, `403`, concealed `404`, conflict `409` and validation `422` behavior;
- warning response shape and OpenAPI contracts.

## Future Charging Session Boundary

Unit tests shall validate Reservation activation and completion domain operations and invariants.
Tests requiring real Charging Session endpoints, HTTP integration or energy interruption are
deferred to SPEC-007.

---

# 22. Acceptance Criteria

## Vehicle

- [ ] Human and Technical Client identities can create multiple owned Vehicles.
- [ ] Owners can list, retrieve and update visible Vehicles.
- [ ] Platform Administrators can manage all Vehicles.
- [ ] Vehicle ownership is immutable and unauthorized resources are concealed.
- [ ] Vehicle can transition between ACTIVE and INACTIVE.
- [ ] INACTIVE Vehicles cannot receive new or rescheduled Reservations.
- [ ] Vehicle history is preserved without physical deletion.

## Reservation Domain

- [ ] Reservation targets one Connector and one owned ACTIVE Vehicle.
- [ ] Intervals use `[start_at, end_at)` semantics.
- [ ] Blocking Connector and Vehicle overlaps return `409 Conflict`.
- [ ] Back-to-back Reservations are accepted.
- [ ] Duration boundaries of 15 minutes and 24 hours are inclusive.
- [ ] Normal cancellation produces CANCELLED.
- [ ] Late cancellation produces LATE_CANCELLED and always remains available before activation.
- [ ] Cancellation releases Connector and Vehicle calendars immediately.
- [ ] No-Show processing is automatic and deterministic.
- [ ] Early Start and Grace Period boundaries are enforced.
- [ ] Early Start does not automatically extend the Reservation.
- [ ] Eligible CONFIRMED Reservations can be explicitly rescheduled.
- [ ] Rescheduling revalidates all temporal, ownership, eligibility and overlap rules.
- [ ] ACTIVE and terminal Reservations are immutable.
- [ ] Only CONFIRMED and ACTIVE block calendars.

## Authorization

- [ ] Human and Technical Client identities can manage only owned workflows.
- [ ] Platform Administrators can manage all Reservations.
- [ ] Facility Operators have read-only visibility for managed Facilities.
- [ ] Researcher and Data Scientist Roles do not grant Reservation mutation rights.

## Persistence

- [ ] Vehicle and Reservation persistence models and constraints are implemented.
- [ ] Reservation owner equals Vehicle owner.
- [ ] timestamps persist as timezone-aware UTC values.
- [ ] historical Vehicle and Reservation references are preserved.
- [ ] terminal Reservations do not block availability queries.
- [ ] concurrent requests cannot create Connector or Vehicle overlaps.

## API and Future Integration

- [ ] Vehicle and Reservation REST contracts and OpenAPI schemas are implemented.
- [ ] synchronous warnings are distinct from future notifications.
- [ ] Reservation exposes domain operations for future activation and completion.
- [ ] SPEC-006 completion does not require Charging Session endpoints or HTTP integration.

---

# 23. Future Integration

## SPEC-007 — Charging Sessions

Reservation exposes domain operations for future activation and completion:

```text
CONFIRMED → ACTIVE → COMPLETED
```

SPEC-007 shall define actual Charging Session endpoints, application integration, session lifecycle
and energy interruption behavior. Charging Sessions shall request Reservation transitions rather
than modifying Reservation persistence directly.

## SPEC-008 — Telemetry

Telemetry may later describe charging activity associated with a Reservation through its Charging
Session. SPEC-006 does not require telemetry ingestion or treat Reservation lifecycle changes as
telemetry measurements.

## SPEC-009 — Domain Events

Future conceptual events may include ReservationCreated, ReservationRescheduled,
ReservationActivated, ReservationCompleted, ReservationCancelled, ReservationLateCancelled and
ReservationNoShow. Messaging and event persistence remain deferred to SPEC-009.

## SPEC-010 — Analytics

Historical data may support no-show, cancellation, lead-time, utilization and demand analysis.

---

# 24. Implementation Guidance

Reservation and Vehicle business rules belong in the Smart Charging domain layer. Application
services coordinate repositories, authorization, infrastructure eligibility and transactions. The
API layer maps DTOs, responses and warnings without implementing lifecycle rules.

The implementation shall use one injectable or otherwise consistent application clock so boundary
and No-Show tests remain deterministic. No scheduler technology or persistence locking strategy is
mandated by this specification.

---

# 25. Final Considerations

SPEC-006 establishes an implementation-ready scheduling model centered on one owner, one Vehicle,
one Connector and one half-open time interval. It introduces only the minimum Vehicle capability
needed by Reservations, preserves Technical Client equivalence for simulation and prepares clean
domain operations for future Charging Sessions without prematurely requiring SPEC-007.
