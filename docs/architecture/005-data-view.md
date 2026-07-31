# Architecture View 005 — Data View

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

This document describes the data architecture of the Smart Charging Experimentation Platform (SCEP).

Its objective is to define how operational information is created, transformed, stored and consumed throughout the platform.

Unlike a traditional database design document, this specification focuses on **data ownership**, **data lifecycle**, **domain events**, **research datasets** and **AI readiness**.

Database implementation details are intentionally omitted.

---

# 2. Data Architecture Principles

The platform adopts the following principles.

## Single Source of Truth

Every business entity has one authoritative owner.

No duplicated transactional data should exist between modules.

---

## Event as Historical Record

Business events represent immutable facts.

Operational history should be reconstructed from events whenever necessary.

---

## Operational vs Analytical Separation

Transactional data and analytical data have different purposes.

Although both are initially stored in PostgreSQL, they represent different logical concerns.

---

## Dataset Reproducibility

Every Version 1 dataset exported by the platform shall provide artifact integrity, provenance and
deterministic generation under equivalent schema, parameters, implementation revision and source
snapshot.

Dataset Export does not guarantee reconstruction of historical source state after it changes.

Simulation reproducibility means rerunning a simulation from its scenario, version, parameters and
seed. It belongs to the external Simulation Engine and is distinct from deterministic Dataset
Export generation.

---

## Read Models

Future Analytics versions may maintain optimized read models.

These models never replace transactional data.

SPEC-010 version 1 instead computes metrics on demand from persisted operational data and does not
persist analytical results.

---

# 3. Data Domains

The platform organizes information into logical domains.

## Identity

Owns:

* Users
* Roles
* Permissions
* Authentication

---

## Smart Charging

Owns:

* Charging Stations
* Connectors
* Vehicles
* Reservations
* Charging Sessions

---

## Telemetry

Owns:

* Telemetry Samples
* Power Measurements
* Energy Measurements
* Battery State
* Device Status

---

## Events

Owns:

* Domain Events
* Event Metadata
* Event History

---

## Analytics

Owns:

* KPI definitions
* read-only analytical projections
* aggregate and time-series response models

---

## AI

Owns:

* immutable Weekly Occupancy Prediction publications and buckets inside SCEP
* limited model, external-run and Dataset Export provenance references inside SCEP

The external AI Research Environment owns model artifacts, feature pipelines and complete
experiment metadata. SCEP does not become a Model Registry or Feature Store.

---

# 4. High-Level Data Flow

```text
Simulation Engine / Users

            │

            ▼

      Business Operation

            │

            ▼

    Transactional Data

       ┌────┴──────────────┐
       ▼                   ▼

Domain Events      Analytics Queries
                           │
                           ▼
                          KPIs

Operational Data / KPIs

            │

            ▼

 Future Dataset Export

            │

            ▼

 Future Machine Learning Models

            │

            ▼

Planned Weekly Occupancy Prediction Publications

            │

            ▼

 Future Operational Dashboard
```

The same operational data simultaneously supports:

* platform execution;
* analytics;
* experimentation;
* artificial intelligence.

---

# 5. Entity Ownership

| Entity           | Owner          |
| ---------------- | -------------- |
| User             | Identity       |
| Role             | Identity       |
| Charging Station | Smart Charging |
| Connector        | Smart Charging |
| Vehicle          | Smart Charging |
| Reservation      | Smart Charging |
| Charging Session | Smart Charging |
| Telemetry Sample | Telemetry      |
| Domain Event     | Events         |
| KPI              | Analytics      |
| Dataset          | Dataset Export |
| Prediction       | AI             |
| Experiment       | AI             |

Only the owning module may modify its entities.

Other modules may consume data through APIs, repositories or events according to architectural rules.

Within Smart Charging, every Charging Session originates from exactly one Reservation, and a
Reservation originates at most one Charging Session. SPEC-007 does not include direct or
otherwise unreserved Charging Sessions.

Telemetry Samples are immutable observations owned by Telemetry. Every Telemetry Sample is
associated with exactly one Charging Session owned by Smart Charging.

---

# 6. Domain Events

Events are first-class data assets.

Each event shall contain, at minimum:

* Event Identifier
* Event Type
* Timestamp
* Aggregate Identifier
* Correlation Identifier
* Producer
* Payload
* Metadata

Example events:

* ReservationCreated
* ReservationRescheduled
* ReservationCancelled
* ReservationMarkedNoShow
* ChargingSessionStarted
* ChargingSessionCompleted
* TelemetrySampleReceived

Events are immutable.

Their business facts, payloads and contracts shall never be updated after persistence. Dispatch
tracking metadata may change without changing the recorded fact.

---

# 7. Data Lifecycle

Every operational record follows the same lifecycle.

```text
Create

↓

Validate

↓

Persist Business State + Event Atomically

↓

Commit

↓

Dispatch Event After Commit

↓

Aggregate

↓

Export

↓

Archive
```

No analytical process may modify transactional records.

This lifecycle is conceptual rather than a mandatory event-to-export dependency. Dataset Export
Version 1 reads operational entities through module-owned read contracts and reuses Analytics
projections as defined by ADR-009.

---

# 8. Dataset Generation

Dataset generation is one of the core capabilities of SCEP.

Datasets may include:

* vehicles;
* reservations;
* charging sessions;
* telemetry;
* occupancy history;
* failures;
* simulation metadata;
* operational KPIs.

Portable export formats are selected by the Dataset Export functional specification. Version 1
supports:

* CSV;
* Parquet.

Every dataset shall contain metadata describing:

* generation date;
* software version;
* source cutoff;
* schema version;
* canonical export configuration;
* integrity information.

Experiment identifiers, feature descriptions, simulation seeds and simulation parameters are
conditional source lineage rather than universal export metadata. A future specification may
introduce a structured `source_lineage` object when the source association can be represented
truthfully.

---

# 9. AI Data Pipeline

```text
Historical Data

↓

Dataset Export

↓

Feature Engineering

↓

Model Training

↓

Validation

↓

Prediction

↓

Prediction Storage

↓

Dashboard
```

The AI pipeline remains external to the transactional application.

Under SPEC-012, Prediction Storage contains one immutable metadata record and exactly 168 unique
weekday/hour buckets per publication, plus an atomic current-publication reference per canonical
Facility, Station or Connector scope. New runs append history; they do not update accepted buckets.
The Backend API validates and serves externally generated values but performs no model inference.

---

# 10. Data Ownership Rules

The following rules are mandatory.

* Transactional data belongs to business modules.
* Events belong to the Events module.
* Analytics never changes business data.
* AI never modifies transactional entities.
* Dataset generation is read-only.
* Simulation data is treated exactly like production data.

---

# 11. Persistence Strategy

The MVP uses a single PostgreSQL instance.

Logical separation shall be enforced by module ownership rather than multiple databases.

Future versions may separate:

* Event Store;
* Analytics Database;
* Time-Series Database;
* Feature Store.

This evolution should not require changes to business logic.

---

# 12. Research Considerations

Data produced by SCEP is itself a research artifact.

The platform is expected to generate:

* deterministic, provenance-rich datasets;
* historical event streams;
* operational indicators;
* AI-ready datasets;
* experiment metadata.

These artifacts support not only the Smart Charging domain but future research in Software Engineering, IoT and Artificial Intelligence.

---

# 13. Relationship with Other Documents

Depends on:

* `001-architecture-vision.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`

Supports:

* all functional specifications;
* database implementation;
* analytics implementation;
* AI experimentation.

---

# 14. Final Considerations

The data architecture of SCEP is intentionally designed around domain ownership, immutable events
and deterministic datasets with explicit provenance.

Rather than treating data as a secondary concern, the platform considers operational information a strategic asset that simultaneously enables system execution, architectural evaluation and scientific experimentation.

This approach aligns the platform with modern Software Engineering practices while providing a robust foundation for future Smart Charging research.
