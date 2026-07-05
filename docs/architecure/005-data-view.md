# SPEC-005 — Data View

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

Every dataset exported by the platform must be reproducible.

The same simulation parameters must produce equivalent datasets.

---

## Read Models

Analytics may maintain optimized read models.

These models never replace transactional data.

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

* KPIs
* Aggregations
* Dashboards
* Read Models

---

## AI

Owns:

* Prediction Results
* Model Metadata
* Experiment Metadata

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

            │

            ▼

      Domain Events

            │

            ▼

     Analytics Pipeline

            │

            ▼

      Research Dataset

            │

            ▼

 Machine Learning Models

            │

            ▼

Prediction Results

            │

            ▼

     Operational Dashboard
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
| Reservation      | Smart Charging |
| Charging Session | Smart Charging |
| Telemetry        | Telemetry      |
| Domain Event     | Events         |
| KPI              | Analytics      |
| Dataset          | Analytics      |
| Prediction       | AI             |
| Experiment       | AI             |

Only the owning module may modify its entities.

Other modules may consume data through APIs, repositories or events according to architectural rules.

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
* ChargingSessionStarted
* ChargingSessionFinished
* TelemetryReceived
* StationFaultDetected
* PredictionGenerated

Events are immutable.

They shall never be updated after persistence.

---

# 7. Data Lifecycle

Every operational record follows the same lifecycle.

```text
Create

↓

Validate

↓

Persist

↓

Publish Event

↓

Consume

↓

Aggregate

↓

Export

↓

Archive
```

No analytical process may modify transactional records.

---

# 8. Dataset Generation

Dataset generation is one of the core capabilities of SCEP.

Datasets may include:

* reservations;
* charging sessions;
* telemetry;
* occupancy history;
* failures;
* simulation metadata;
* operational KPIs.

Supported export formats:

* CSV;
* JSON;
* Parquet.

Every dataset shall contain metadata describing:

* generation date;
* simulation seed;
* software version;
* experiment identifier;
* export configuration.

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

* reproducible datasets;
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

The data architecture of SCEP is intentionally designed around domain ownership, immutable events and reproducible datasets.

Rather than treating data as a secondary concern, the platform considers operational information a strategic asset that simultaneously enables system execution, architectural evaluation and scientific experimentation.

This approach aligns the platform with modern Software Engineering practices while providing a robust foundation for future Smart Charging research.
