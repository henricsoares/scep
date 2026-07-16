# ADR-003 — Adopt Event-Driven Internal Architecture

**Status:** Accepted
**Date:** 2026
**Related Specs:**

* `001-architecture-vision.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`
* `005-data-view.md`
* `006-quality-attributes.md`

---

# Context

The Smart Charging Experimentation Platform (SCEP) integrates multiple functional areas, including:

* Smart Charging;
* Telemetry;
* Analytics;
* Dataset Export;
* Artificial Intelligence;
* Observability.

Although these capabilities execute within a single Backend API, they represent distinct concerns with different responsibilities and evolution rates.

Additionally, one of the primary goals of SCEP is to transform operational activity into research artifacts such as datasets, metrics and prediction inputs.

Traditional synchronous interactions between modules would introduce unnecessary coupling and make it difficult to evolve analytical capabilities independently from transactional business logic.

---

# Decision

The Backend API will adopt an **Event-Driven Architecture (EDA)** for internal communication between application modules.

Business operations shall publish **Domain Events** representing immutable business facts.

Interested modules may consume these events without introducing direct dependencies between producers and consumers.

The initial implementation will use a persistent **Event Store** and an in-process **Internal Event
Dispatcher** with transactional persistence, dispatch after commit and at-least-once delivery. It
remains compatible with a future Outbox + Kafka transport.

---

# Rationale

Event-Driven Architecture aligns naturally with the objectives of SCEP.

Every relevant business operation already produces information that is valuable for:

* operational analytics;
* dataset generation;
* observability;
* future integrations;
* artificial intelligence.

Instead of explicitly invoking every downstream capability, business modules simply publish events describing what happened.

This approach preserves transactional simplicity while allowing new consumers to be introduced without modifying existing business workflows.

---

# Alternatives Considered

## Direct Service Calls

Business modules invoke one another directly.

Advantages:

* simple implementation;
* easy debugging.

Rejected because it creates strong coupling between business domains and analytical components.

Adding new consumers would require modifying existing modules.

---

## External Message Broker

Use Kafka, RabbitMQ or another messaging platform from the beginning.

Advantages:

* distributed scalability;
* asynchronous processing;
* independent services.

Rejected because the current architecture is a Modular Monolith and does not require distributed infrastructure.

The operational complexity would outweigh the expected benefits during the initial stages of the project.

---

## Internal Event Bus

Business modules publish events to an internal dispatcher.

Consumers subscribe to relevant event types.

Selected because it preserves loose coupling while maintaining a simple deployment model.

---

# Consequences

## Positive Consequences

* reduced coupling between modules;
* easier introduction of new analytical capabilities;
* natural integration with observability;
* simpler dataset generation;
* improved architectural extensibility;
* clear representation of business history.

---

## Negative Consequences

* increased implementation complexity compared to direct method calls;
* asynchronous execution paths may be harder to debug;
* event versioning must be managed carefully;
* developers must understand eventual consistency concepts where applicable.

---

# Architectural Rules

The following rules apply to all Domain Events.

* Events represent facts that already occurred.
* Events are immutable.
* Events shall never contain business behavior.
* Events must be persisted before becoming available for analytical processing.
* Events must not trigger transactional validation in other modules.
* Events shall be versionable.
* Events must include sufficient metadata for traceability.

---

# Event Structure

Every Domain Event shall contain, at minimum:

* Event Identifier;
* Event Type;
* Aggregate Identifier;
* Aggregate Type;
* Timestamp;
* Correlation Identifier;
* Producer Module;
* Payload;
* Metadata.

This standardization enables analytics, tracing and dataset generation.

---

# Initial Domain Events

The initial catalog is defined by SPEC-009 and includes:

## Reservation

* ReservationCreated
* ReservationRescheduled
* ReservationCancelled
* ReservationMarkedNoShow

---

## Charging

* ChargingSessionStarted
* ChargingSessionCompleted

---

## Telemetry

* TelemetrySampleReceived

Analytics, Dataset Export, AI and Digital Twin are future consumers. New producers or event types
require subsequent specifications.

---

# Event Flow

A typical event lifecycle is illustrated below.

```text
HTTP Request

      │

      ▼

Business Validation

      │

      ▼

State Change

      │

      ▼

Persist Business State + Event

      │

      ▼

Commit Transaction

      │

      ▼

Dispatch Persisted Domain Event

      │

      ▼

Internal Event Dispatcher

      │

 ┌────┼───────────┬─────────────┐

 ▼    ▼           ▼             ▼

Analytics

Dataset Export

Observability

Notification
```

Every consumer operates independently from the business transaction that originated the event.

---

# Event Consumers

The following are future consumers:

## Analytics Component

Consumes business events to calculate KPIs and operational indicators.

---

## Dataset Export Component

Consumes historical events to generate reproducible research datasets.

---

## Notification Component

Consumes selected events to generate user notifications.

---

Future consumers may include:

* external integrations;
* anomaly detection;
* real-time dashboards;
* stream processing services.

---

# Relationship with Transactional Data

Transactional entities remain the authoritative business state.

Domain Events complement, but do not replace, transactional persistence.

The platform follows the principle:

> **Business state answers "what is true now"; Domain Events answer "what happened over time."**

This distinction is fundamental for supporting both operational workflows and research activities.

---

# Quality Attributes Supported

This decision primarily supports:

| Quality Attribute | Support                                                     |
| ----------------- | ----------------------------------------------------------- |
| Extensibility     | New consumers may be introduced without modifying producers |
| Maintainability   | Reduced coupling between modules                            |
| Observability     | Events enrich logs, metrics and traces                      |
| Reproducibility   | Event history supports experiment reconstruction            |
| Testability       | Producers and consumers may be tested independently         |
| Data Quality      | Events provide immutable historical records                 |

---

# Risks and Mitigations

## Risk: Excessive Event Proliferation

Too many event types may increase complexity.

Mitigation:

* define clear naming conventions;
* document event schemas;
* periodically review unused events.

---

## Risk: Tight Coupling Through Payloads

Consumers may become dependent on specific payload structures.

Mitigation:

* version event contracts;
* keep payloads focused on business facts;
* avoid exposing internal implementation details.

---

## Risk: Hidden Execution Paths

Indirect event processing may make debugging more difficult.

Mitigation:

* structured logging;
* distributed tracing;
* correlation identifiers;
* event persistence.

---

# Future Evolution

The initial implementation uses a persistent Event Store and an in-process Internal Event
Dispatcher. Business state and its Domain Events are persisted in one transaction; dispatch starts
only after commit and uses at-least-once delivery.

Future versions may migrate to an external messaging platform if justified by scalability or distribution requirements.

A subsequent specification may add an Outbox publisher and Kafka transport. This evolution shall
preserve producer responsibilities, Domain Event contracts, transactional persistence and
at-least-once consumer semantics. Replacing current dispatcher responsibilities requires an
explicit subsequent architectural decision.

---

# Decision Outcome

The Backend API will adopt an internal Event-Driven Architecture in which Domain Events represent immutable business facts and enable communication between modules.

This decision reduces coupling, improves extensibility and transforms operational activity into reusable assets for analytics, observability and artificial intelligence, directly supporting the research objectives of the Smart Charging Experimentation Platform.
