# ADR-004 — Adopt PostgreSQL as the Primary Data Store

**Status:** Accepted
**Date:** 2026
**Related Specs:**

* `001-architecture-vision.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`
* `005-data-view.md`
* `006-quality-attributes.md`
* `008-deployment-runtime-view.md`

---

# Context

The Smart Charging Experimentation Platform (SCEP) manages operational data, telemetry, domain events, analytics and research artifacts.

The backend must support:

* transactional consistency;
* relational business entities;
* event persistence;
* analytical queries;
* dataset generation;
* future architectural evolution.

Additionally, the platform is intended to remain reproducible and simple to execute in local development environments while still supporting realistic research scenarios.

---

# Decision

SCEP will adopt **PostgreSQL** as its primary relational database management system.

A single PostgreSQL instance will initially support all application modules while preserving logical separation through domain ownership rather than physical database separation.

Each application module owns its data model and accesses it exclusively through its own repositories.

---

# Rationale

PostgreSQL provides an excellent balance between transactional reliability, analytical capabilities and ecosystem maturity.

It supports:

* ACID transactions;
* relational modeling;
* JSON document storage;
* indexing strategies;
* mature migration tooling;
* Docker-based deployment;
* excellent integration with Python.

The platform does not currently require multiple databases or polyglot persistence.

Keeping a single relational database simplifies:

* local development;
* automated testing;
* reproducibility;
* deployment;
* backup strategies.

This decision aligns with the Modular Monolith architecture adopted by the Backend API.

---

# Alternatives Considered

## MySQL

MySQL is a mature relational database widely adopted in enterprise applications.

Advantages:

* broad ecosystem;
* strong community support.

Rejected because PostgreSQL provides richer SQL features, stronger JSON capabilities and greater flexibility for analytical workloads.

---

## MongoDB

MongoDB offers schema flexibility and document-oriented persistence.

Advantages:

* flexible document model;
* simple schema evolution.

Rejected because the platform's transactional domain is naturally relational and requires strong consistency between business entities.

The research benefits of relational integrity outweigh the flexibility offered by a document database.

---

## Time-Series Database

Databases such as InfluxDB or TimescaleDB were considered for telemetry storage.

Advantages:

* optimized time-series queries;
* efficient retention policies.

Rejected for the MVP because PostgreSQL adequately supports the expected telemetry volume while reducing infrastructure complexity.

Future versions may introduce specialized storage if justified.

---

## Polyglot Persistence

Using multiple specialized databases.

Example:

* PostgreSQL;
* MongoDB;
* Redis;
* Time-Series Database.

Rejected because the additional operational complexity is not justified during the first implementation of the platform.

---

# Consequences

## Positive Consequences

* simplified architecture;
* transactional consistency;
* mature tooling;
* easy Docker deployment;
* excellent Python ecosystem;
* simplified backups;
* easier onboarding.

---

## Negative Consequences

* analytical and transactional workloads share the same database;
* telemetry volume may eventually require specialized storage;
* scalability remains vertically oriented during the MVP.

---

# Architectural Rules

The following rules apply.

* PostgreSQL is the authoritative transactional data store.
* External systems shall never access PostgreSQL directly.
* Every module owns its own persistence layer.
* Database access occurs exclusively through repositories.
* Business logic shall never depend on SQL statements.
* Schema evolution shall be managed through migrations.
* Raw SQL should be used only when justified by measurable performance or analytical requirements.

---

# Logical Data Ownership

Although a single PostgreSQL instance is used, ownership remains modular.

| Module            | Owns                                                  |
| ----------------- | ----------------------------------------------------- |
| Identity & Access | Users, Roles, Permissions                             |
| Smart Charging    | Stations, Connectors, Reservations, Charging Sessions |
| Telemetry         | Telemetry Records                                     |
| Domain Events     | Event Store                                           |
| Analytics         | Aggregated Metrics                                    |
| Prediction        | Prediction Results                                    |

Modules must not manipulate entities owned by other modules.

Cross-module interaction shall occur through services or Domain Events.

---

# Persistence Strategy

The platform follows a layered persistence architecture.

```text
Application Service

        │

        ▼

Repository

        │

        ▼

SQLAlchemy

        │

        ▼

PostgreSQL
```

Repositories isolate persistence concerns from business logic.

This abstraction allows persistence implementation details to evolve independently from application behavior.

---

# Migration Strategy

Database schema evolution shall be managed using **Alembic**.

Every schema modification must:

* be version controlled;
* be reproducible;
* support automated execution;
* be compatible with CI environments.

Manual schema changes are prohibited.

---

# Data Categories

PostgreSQL stores several categories of information.

## Transactional Data

Examples:

* users;
* reservations;
* charging sessions;
* charging stations.

---

## Operational Data

Examples:

* telemetry;
* equipment status;
* connector information.

---

## Historical Data

Examples:

* domain events;
* simulation executions;
* experiment metadata.

---

## Analytical Data

Examples:

* KPIs;
* occupancy indicators;
* aggregated statistics.

---

## AI Metadata

Examples:

* exported datasets;
* prediction results;
* experiment references.

---

# Relationship with Domain Events

Domain Events are persisted in PostgreSQL before being consumed by analytical components.

The database therefore stores:

* current business state;
* historical event stream.

This approach supports:

* reproducible research;
* analytics;
* dataset generation;
* architectural traceability.

---

# Backup and Recovery

Although production deployment is outside the project scope, the architecture assumes that PostgreSQL supports:

* logical backups;
* point-in-time recovery;
* migration replay;
* containerized persistence volumes.

Development environments rely on Docker volumes for persistence.

---

# Quality Attributes Supported

This decision primarily supports:

| Quality Attribute | Support                                    |
| ----------------- | ------------------------------------------ |
| Reliability       | ACID transactions and mature persistence   |
| Data Quality      | Strong relational consistency              |
| Maintainability   | Mature tooling and clear migration process |
| Reproducibility   | Deterministic schema versioning            |
| Testability       | Containerized database execution           |
| Simplicity        | Single database architecture               |

---

# Risks and Mitigations

## Risk: Database Growth

Telemetry and event history may grow significantly.

Mitigation:

* indexing strategy;
* archival policies;
* future analytical storage separation.

---

## Risk: Mixed Workloads

Transactional and analytical queries may compete for resources.

Mitigation:

* optimized indexes;
* aggregated read models;
* future analytical database if required.

---

## Risk: Schema Evolution

Frequent schema changes may impact compatibility.

Mitigation:

* Alembic migrations;
* backward-compatible changes whenever possible;
* automated migration testing.

---

# Future Evolution

The initial architecture intentionally favors simplicity.

Future evolution may introduce specialized persistence technologies when justified.

Potential future additions include:

* Redis for caching;
* TimescaleDB for telemetry;
* object storage for datasets;
* Feature Store for machine learning;
* dedicated analytical database.

These additions should complement PostgreSQL rather than replace it as the authoritative transactional database.

---

# Decision Outcome

PostgreSQL is adopted as the primary database management system for SCEP.

Its relational model, transactional guarantees, mature ecosystem and compatibility with Python provide a solid foundation for the Smart Charging domain while supporting analytics, domain events and research datasets within a single, reproducible architecture.

Future persistence technologies may be incorporated incrementally without altering the architectural principles established by the platform.
