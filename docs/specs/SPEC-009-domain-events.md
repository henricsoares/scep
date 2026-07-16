# SPEC-009 — Domain Events

## Smart Charging Experimentation Platform (SCEP)

**Status:** Draft

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

This specification defines the Domain Events capability of the Smart Charging Experimentation Platform (SCEP).

Domain Events represent immutable business facts that have already occurred within the platform.

Their purpose is to decouple operational workflows from downstream consumers while preserving a complete and reliable history of business events.

This specification defines:

- Domain Event Aggregate;
- Event Store;
- Internal Event Dispatcher;
- event publication;
- event persistence;
- dispatch lifecycle;
- event versioning;
- event contracts;
- authorization;
- observability.

The implementation is intentionally designed as an internal event infrastructure suitable for an academic experimentation platform.

External messaging systems remain outside the scope of this specification.

---

# 2. Scope

This specification includes:

- Domain Event Aggregate;
- Event Store;
- internal event publication;
- internal event dispatch;
- event persistence;
- event versioning;
- event lifecycle;
- event querying;
- REST API;
- authorization;
- OpenAPI;
- observability;
- testing requirements.

---

## Out of Scope

The following capabilities are intentionally deferred.

- Kafka;
- RabbitMQ;
- MQTT;
- Apache Pulsar;
- EventBridge;
- Webhooks;
- external event brokers;
- distributed event buses;
- event replay;
- event sourcing;
- saga orchestration;
- CQRS;
- cross-service messaging.

Future versions may introduce external brokers without changing the Domain Event contracts defined by this specification.

The documented initial implementation uses a persistent Event Store and an in-process Internal
Event Dispatcher. This specification is not yet implemented.

This architectural decision allows a future specification to add an Outbox and Kafka transport
without changing producer responsibilities or existing event contracts.

---

# 3. Relationship with Existing Domains

Domain Events are produced by business operations executed in other platform domains.

A Domain Event never owns business state.

Instead, it records that a business fact has already occurred.

The initial producers are:

- Reservation;
- Charging Session;
- Telemetry.

Future specifications may introduce additional producers.

---

## Relationship

```text
Reservation

        │

        ├──────────────┐

        ▼              │

Charging Session       │

        │              │

        ▼              │

TelemetrySample        │

        │              │

        └──────┬───────┘

               ▼

          Domain Event
```

A single business operation may produce one or more Domain Events.

Every Domain Event shall reference exactly one Aggregate instance.

The Aggregate itself never depends on downstream consumers.

---

# 4. Domain Model

The Domain Event Aggregate represents one immutable business fact. Its identifiers, contract,
payload, metadata and business timestamps are immutable after persistence. Delivery tracking is
mutable operational metadata and does not alter that fact.

A Domain Event is created only after a business operation has been successfully validated.

Once persisted, its business data shall never be modified. Only dispatch tracking fields may be
updated by the Internal Event Dispatcher.

---

## DomainEvent

```text
DomainEvent

id

event_type
event_version

aggregate_id
aggregate_type

producer_module

occurred_at
recorded_at

correlation_id
causation_id

payload
metadata

dispatch_status
dispatch_attempts
last_dispatch_at
last_error

created_at
```

---

## Attributes

### id

Globally unique identifier of the Domain Event.

Immutable.

---

### event_type

Stable identifier representing the published contract.

Examples:

```text
reservation.created

reservation.cancelled

charging-session.started

telemetry.sample-received
```

Immutable.

---

### event_version

Version of the published contract.

Mandatory.

Initial value:

```text
1
```

Future contract evolution shall increment this value without changing the meaning of previous versions.

---

### aggregate_id

Identifier of the Aggregate that originated the event.

Mandatory.

Immutable.

---

### aggregate_type

Aggregate type that produced the event.

Examples:

```text
Reservation

ChargingSession

TelemetrySample
```

Mandatory.

Immutable.

---

### producer_module

Logical module responsible for publishing the event.

Examples:

```text
charging

telemetry
```

Mandatory.

Immutable.

---

### occurred_at

Timestamp representing when the business fact occurred.

Mandatory.

Immutable.

---

### recorded_at

Timestamp assigned by the platform when the Domain Event is persisted.

Mandatory.

Immutable.

---

### correlation_id

Identifier used to correlate multiple events belonging to the same business workflow.

Optional.

When available, it shall remain unchanged across the entire workflow.

Example:

```text
HTTP Request

        │

ReservationCreated

        │

ChargingSessionStarted

        │

TelemetrySampleReceived
```

---

### causation_id

Identifier of the command or Domain Event that directly caused this event.

Optional.

Future specifications may require causation tracking for chained event processing.

---

### payload

Versioned JSON document containing event-specific business information.

Mandatory.

Immutable.

The payload shall include only information necessary to describe the business fact.

It shall not duplicate the complete Aggregate state.

---

### metadata

Additional technical information associated with the event.

Examples include:

- authenticated actor;
- account type;
- request identifier;
- trace identifier.

Sensitive information shall never be stored in metadata.

Metadata is immutable after persistence.

---

### dispatch_status

Current dispatch lifecycle state.

Supported values:

```text
PENDING

DISPATCHED

FAILED
```

Managed exclusively by the Internal Event Dispatcher.

---

### dispatch_attempts

Number of dispatch attempts performed by the Internal Event Dispatcher.

Automatically maintained.

---

### last_dispatch_at

Timestamp of the most recent dispatch attempt.

Null until the first dispatch attempt.

---

### last_error

Implementation-defined description of the most recent dispatch failure.

Null while dispatch succeeds.

This field exists exclusively for operational visibility.

It shall never modify the original business meaning of the Domain Event.

---

### created_at

Persistence timestamp.

Automatically assigned.

Immutable.

---

# 5. Ubiquitous Language

## Domain Event

An immutable business fact representing something that has already occurred.

Domain Events are produced only after successful business operations.

---

## Event Producer

The Aggregate responsible for publishing a Domain Event.

Initial producers are:

- Reservation;
- ChargingSession;
- TelemetrySample.

---

## Event Consumer

An internal platform component interested in one or more Domain Events.

Consumers execute independently from the original business transaction.

Examples include:

- Analytics;
- Dataset Export;
- future Notification;
- future AI components.

Producers never depend on consumers.

---

## Event Store

The persistent repository responsible for storing every Domain Event.

The Event Store provides:

- immutable event history;
- dispatch tracking;
- event querying;
- durable records that a future specification could use to define replay.

The Event Store is the authoritative source of Domain Events.

---

## Internal Event Dispatcher

Infrastructure component responsible for delivering persisted Domain Events to registered consumers.

The dispatcher operates only after the originating database transaction has been committed.

It provides at-least-once delivery, so a consumer may receive the same persisted event more than
once and shall be idempotent.

---

## Event Contract

The versioned structure describing one event type.

Event contracts evolve through versioning.

Existing versions shall remain compatible with previously persisted events.

---

## Correlation

Association of multiple Domain Events belonging to the same business workflow.

Correlation enables end-to-end traceability across multiple Aggregates.

---

## Causation

Relationship between one Domain Event and the operation that directly produced it.

Causation is optional in the initial implementation.

---

# 6. Event Lifecycle

Every Domain Event follows the lifecycle below.

```text
Business Operation

        │

        ▼

Domain Event Created

        │

        ▼

Persisted

        │

        ▼

PENDING

        │

        ▼

Dispatch Attempt

   ┌───────────────┐
   │               │
   ▼               ▼

DISPATCHED      FAILED
```

The lifecycle concerns only delivery.

It never changes the business meaning of the event.

---

## Creation

A Domain Event is created only after the associated business operation has been successfully validated.

Validation failures shall never produce Domain Events.

---

## Persistence

Business state and Domain Event shall be persisted within the same PostgreSQL transaction.

If the transaction commits successfully:

- business state exists;
- Domain Event exists.

If the transaction is rolled back:

- business state does not exist;
- Domain Event does not exist.

The implementation shall never persist one without the other.

---

## Dispatch

Dispatch begins only after the successful transaction commit.

The dispatcher retrieves pending Domain Events from the Event Store and invokes registered consumers.

Dispatch occurs outside the original business transaction.

Consumer failures shall never roll back the originating Aggregate.

---

## Failure

Consumer failures change only:

```text
dispatch_status

dispatch_attempts

last_dispatch_at

last_error
```

The recorded business fact and its event contract remain immutable.

---

## Retry

Failed dispatches may be retried.

Retries shall not modify:

- event payload;
- metadata;
- identifiers;
- timestamps describing the business fact.

Only dispatch metadata may change.

---

# 7. Business Rules

## BR-001 — Immutable Events

Every Domain Event records an immutable business fact.

Updates to identifiers, event contracts, business timestamps, payload and metadata are prohibited
after persistence. Only delivery tracking fields may change.

---

## BR-002 — Business Facts Only

Domain Events represent facts that have already occurred.

Commands, requests or intentions shall never be published as Domain Events.

Examples:

Valid:

```text
ReservationCreated

ChargingSessionCompleted
```

Invalid:

```text
CreateReservation

CompleteChargingSession
```

---

## BR-003 — Transactional Consistency

Business state and Domain Event shall be persisted within the same database transaction.

The platform shall never expose a committed Aggregate without its corresponding Domain Event.

Likewise, a rolled-back Aggregate shall never leave behind a persisted Domain Event.

---

## BR-004 — Dispatch After Commit

Consumers shall receive Domain Events only after the originating transaction has been committed.

Consumers shall never participate in the original business transaction.

---

## BR-005 — At-Least-Once Delivery

The Internal Event Dispatcher provides at-least-once delivery.

Consumers may receive the same Domain Event more than once.

Consumers shall therefore be idempotent.

Exactly-once delivery is outside the scope of this specification.

---

## BR-006 — Stable Event Contracts

Every event contract is versioned.

Future changes shall increment:

```text
event_version
```

without modifying previously published versions.

---

## BR-007 — Producer Independence

Event producers shall never depend on:

- Analytics;
- Dataset Export;
- Notification;
- AI components;
- future consumers.

A producer only publishes a Domain Event.

Consumer execution remains entirely independent.

---

## BR-008 — Internal Dispatch Only

This specification defines only an Internal Event Dispatcher.

Domain Events shall not be published directly to:

- Kafka;
- RabbitMQ;
- MQTT;
- EventBridge;
- Webhooks;
- external messaging systems.

Future specifications may introduce external brokers without changing the published Domain Event contracts.

---

## BR-009 — Event Store Authority

Every published Domain Event shall be persisted in the Event Store before dispatch begins.

Consumers shall receive only persisted Domain Events.

The Event Store is the authoritative source of truth for event history.

---

## BR-010 — No Historical Backfill

Domain Events shall be generated only for business operations executed after this specification becomes active.

Previously persisted business records shall not generate reconstructed Domain Events automatically.

Future specifications may define explicit historical import mechanisms.

---

# 8. Initial Event Catalog

When SPEC-009 is implemented, the initial producers shall publish the following Domain Events.

---

## Reservation

### ReservationCreated

Published after a Reservation is successfully created.

Producer:

```text
Reservation
```

---

### ReservationRescheduled

Published after a Reservation is successfully rescheduled.

Producer:

```text
Reservation
```

---

### ReservationCancelled

Published after a Reservation is successfully cancelled.

The payload shall distinguish between:

```text
STANDARD

LATE
```

cancellation types.

Separate event types for late cancellation are intentionally not introduced.

Producer:

```text
Reservation
```

---

### ReservationMarkedNoShow

Published when a Reservation transitions to the NO_SHOW state.

Producer:

```text
Reservation
```

---

## Charging Session

### ChargingSessionStarted

Published after a Charging Session is successfully created and activated.

Producer:

```text
ChargingSession
```

---

### ChargingSessionCompleted

Published after a Charging Session completes successfully.

Producer:

```text
ChargingSession
```

---

## Telemetry

### TelemetrySampleReceived

Published after a TelemetrySample is successfully persisted.

One TelemetrySample produces exactly one Domain Event.

The event payload may contain one or more measurements depending on the received observation.

Producer:

```text
TelemetrySample
```

---

# 9. REST API

The Event Store provides a read-only administrative API.

Domain Events are never created through REST endpoints.

Publishing occurs exclusively through business operations executed by other platform modules.

---

## List Domain Events

```http
GET /domain-events
```

Returns Domain Events visible to the authenticated actor.

Supported filters include:

- event_type;
- aggregate_type;
- aggregate_id;
- producer_module;
- occurred_from;
- occurred_to;
- dispatch_status.

Default ordering:

```text
occurred_at DESC

id DESC
```

Pagination follows the existing platform conventions.

---

Possible responses:

```text
200 OK
401 Unauthorized
403 Forbidden
```

---

## Retrieve Domain Event

```http
GET /domain-events/{eventId}
```

Returns one persisted Domain Event.

Possible responses:

```text
200 OK
401 Unauthorized
403 Forbidden
404 Not Found
```

---

No endpoint exists for:

- POST;
- PUT;
- PATCH;
- DELETE.

Domain Event business data is immutable; the endpoint does not expose delivery metadata updates.

---

# 10. Authorization

Authorization follows the platform model established by SPEC-005.

---

## Platform Administrator

Platform Administrators may:

- list Domain Events;
- retrieve Domain Events;
- inspect dispatch status;
- inspect payloads and metadata.

Platform Administrators have global visibility.

---

## Facility Operator

Facility Operators shall not access the Event Store.

---

## Human Account

Human Accounts shall not access the Event Store.

Business workflows continue to operate normally, but Domain Events remain internal platform artifacts.

---

## Technical Client

Technical Clients shall not access the Event Store.

---

## Researcher

Researchers shall not access the Event Store in this specification.

Future analytical specifications may introduce controlled read access.

---

## Data Scientist

Data Scientists shall not access the Event Store in this specification.

Future analytical specifications may introduce controlled read access.

---

# 11. Persistence

Domain Events use Event Store records separate from their originating Aggregate records, while
both records are persisted atomically in the same PostgreSQL transaction.

The persistence model shall include, at minimum:

```text
domain_events

id

event_type
event_version

aggregate_id
aggregate_type

producer_module

occurred_at
recorded_at

correlation_id
causation_id

payload
metadata

dispatch_status
dispatch_attempts
last_dispatch_at
last_error

created_at
```

The persistence model shall enforce:

- primary key;
- immutable payload;
- immutable business metadata;
- valid dispatch status;
- timezone-aware timestamps;
- event version;
- JSON payload validation.

The Event Store shall prevent physical deletion of persisted Domain Events.

Historical records are permanent.

Only the Internal Event Dispatcher may update dispatch metadata, and those updates do not change
the immutable business fact.

---

# 12. Observability

Domain Event publication shall expose operational metrics consistent with the platform observability model.

Metrics shall avoid high-cardinality labels.

At minimum, the implementation shall expose:

- Domain Events published;
- Domain Events dispatched;
- dispatch failures;
- dispatch retries;
- pending Domain Events;
- registered consumers.

Structured logs shall be emitted for:

- event publication;
- dispatch attempts;
- successful dispatch;
- dispatch failures;
- consumer execution.

Logs shall include, whenever available:

- event identifier;
- event type;
- aggregate identifier;
- correlation identifier;
- trace identifier.

Sensitive business information shall never be written to logs.

---

# 13. OpenAPI

The generated OpenAPI documentation shall include:

- DomainEvent schema;
- Event Type enumeration;
- Dispatch Status enumeration;
- administrative query endpoints;
- authentication requirements;
- filtering parameters;
- pagination;
- response examples.

Bearer authentication shall be declared for every protected endpoint.

Example payloads shall be provided for:

- ReservationCreated;
- ReservationCancelled;
- ChargingSessionStarted;
- ChargingSessionCompleted;
- TelemetrySampleReceived.

---

# 14. Acceptance Criteria

The implementation shall satisfy the following acceptance criteria.

---

## Domain Event

- DomainEvent Aggregate implemented.
- Event Store implemented.
- Internal Event Dispatcher implemented.
- Immutable persistence implemented.
- Versioned event contracts implemented.

---

## Event Publication

- Reservation publishes the defined events.
- Charging Session publishes the defined events.
- Telemetry publishes the defined events.
- No duplicate publication occurs for a single business operation.

---

## Transactional Consistency

- Business state and Domain Event are persisted in the same transaction.
- Rolled-back business operations produce no Domain Events.
- Committed business operations always produce their corresponding Domain Events.

---

## Event Dispatch

- Dispatch begins only after transaction commit.
- Pending events are delivered by the Internal Event Dispatcher.
- Dispatch metadata is updated correctly.
- Consumer failures do not roll back business operations.

---

## Authorization

- Platform Administrator access validated.
- Non-administrative actors denied access.
- Event Store remains protected.
- Administrative endpoints enforce authentication.

---

## Persistence

- Event Store migration implemented.
- Immutable payload enforced.
- Dispatch metadata persisted.
- Historical records preserved.
- Event contracts versioned.

---

## API

- Administrative endpoints documented.
- Filtering supported.
- Pagination supported.
- Stable HTTP contracts implemented.
- OpenAPI generated successfully.

---

## Observability

- Metrics exposed.
- Structured logs emitted.
- Dispatch failures observable.
- Pending events measurable.

---

# 15. Testing Requirements

The implementation shall include automated tests covering:

---

## Domain

- DomainEvent creation.
- Immutable behavior.
- Contract versioning.
- Payload validation.
- Metadata validation.

---

## Publication

- ReservationCreated publication.
- ReservationRescheduled publication.
- ReservationCancelled publication.
- ReservationMarkedNoShow publication.
- ChargingSessionStarted publication.
- ChargingSessionCompleted publication.
- TelemetrySampleReceived publication.

---

## Transactional Consistency

- Commit persists both Aggregate and Domain Event.
- Rollback persists neither.
- Event Store integrity preserved.

---

## Dispatch

- Pending events dispatched.
- Successful dispatch updates status.
- Failed dispatch records retry metadata.
- Multiple dispatch attempts supported.
- Consumers execute after commit.

---

## Authorization

- Platform Administrator access.
- Human Account denied.
- Technical Client denied.
- Facility Operator denied.
- Researcher denied.
- Data Scientist denied.

---

## API

- List Domain Events.
- Retrieve Domain Event.
- Filtering.
- Pagination.
- Authentication.
- Authorization.
- OpenAPI validation.

---

## Persistence

- Migration.
- Event Store constraints.
- Immutable persistence.
- Dispatch metadata updates.
- Historical preservation.

---

## Docker Compose

A complete smoke test shall validate:

- automatic migrations;
- backend health;
- Reservation publication;
- Charging Session publication;
- Telemetry publication;
- Event Store persistence;
- administrative API;
- OpenAPI;
- Prometheus metrics;
- Grafana dashboards;
- existing business workflows remain unaffected.

---

# 16. Future Integration

This specification establishes the internal event infrastructure of the Smart Charging Experimentation Platform.

Future specifications may consume or extend this infrastructure with:

- Kafka;
- RabbitMQ;
- MQTT;
- Apache Pulsar;
- Webhooks;
- EventBridge;
- Analytics;
- Dataset Export;
- AI pipelines;
- Digital Twin execution;
- Notification services.

Analytics, Dataset Export, AI and Digital Twin capabilities shall be future consumers of the
existing Domain Event contracts. They are not part of the initial implementation.

The future Outbox + Kafka evolution may add an Outbox publisher and Kafka transport without
changing the responsibilities defined here for producers, transactional event persistence or
post-commit delivery. Any replacement of the Internal Event Dispatcher requires a subsequent
specification. That evolution shall not change:

- producers;
- Domain Event contracts;
- Aggregate behavior;
- at-least-once consumer semantics.

---

# 17. Dependencies

Domain Events depend on previously implemented platform capabilities.

The implementation requires:

- SPEC-005 — Identity and Access;
- SPEC-006 — Reservations;
- SPEC-007 — Charging Sessions;
- SPEC-008 — Telemetry.

This specification does not redefine concepts already owned by those modules.

In particular:

- authentication and authorization remain governed by SPEC-005;
- Reservation lifecycle remains governed by SPEC-006;
- Charging Session lifecycle remains governed by SPEC-007;
- Telemetry ownership and ingestion remain governed by SPEC-008.

Whenever an earlier specification defines business behavior, that specification takes precedence.

---

# 18. Implementation Notes

The implementation shall preserve the layered architecture established by the platform.

In particular:

- Aggregates publish Domain Events but never dispatch them directly.
- Event publication remains independent from consumers.
- The Event Store is the single source of truth for persisted Domain Events.
- The Internal Event Dispatcher operates only after successful transaction commit.
- Consumers execute independently from the originating business transaction.
- Consumer failures affect only dispatch metadata.
- Domain Event payloads remain immutable after persistence.
- Event contracts evolve exclusively through versioning.

The initial implementation intentionally favors simplicity and determinism over distributed messaging.

The combination of transactional Event Store persistence and a post-commit Internal Event
Dispatcher with at-least-once delivery provides a reliable foundation for experimentation. A
future Outbox + Kafka transport can preserve these responsibilities and semantics.

---

# 19. Specification Summary

This specification introduces the event-driven foundation of the Smart Charging Experimentation Platform.

Business Aggregates remain responsible for enforcing domain rules.

Domain Events record completed business facts.

The Event Store preserves those facts.

The Internal Event Dispatcher delivers them to interested consumers.

```text
Reservation
        │
        ▼
ReservationCreated
        │
        ▼
Event Store
        │
        ▼
Internal Event Dispatcher
        │
   ┌────┴──────────────┐
   ▼                   ▼
   Future Analytics   Future Dataset Export
```

This architecture keeps producers independent from consumers while preserving a complete, immutable and versioned business history.

The initial implementation intentionally avoids external messaging infrastructure.

Future specifications may introduce Kafka or other brokers without changing the published Domain
Event contracts or current producer and persistence responsibilities. Analytics, Dataset Export,
AI and Digital Twin remain future consumers.

---

# End of Specification
