# SPEC-002 — Domain Model and Ubiquitous Language

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

This specification defines the business domain of the **Smart Charging Experimentation Platform (SCEP)**.

Its primary objective is to establish a common language shared by developers, researchers and future stakeholders, ensuring that every architectural decision, software component and business feature is based on the same domain concepts.

Unlike implementation specifications, this document intentionally focuses on **business meaning rather than technical implementation**.

It defines:

* ubiquitous language;
* domain boundaries;
* core concepts;
* business actors;
* high-level business relationships;
* business responsibilities.

All subsequent functional specifications shall adopt the terminology established in this document.

---

# 2. Scope

This specification defines the conceptual model of the platform.

It intentionally does **not** describe:

* REST APIs;
* database schema;
* software architecture;
* authentication;
* implementation details.

Those concerns are addressed by other specifications.

---

# 3. Domain Vision

The Smart Charging Experimentation Platform is **not** a charging station controller.

Instead, it is a platform designed to observe, simulate and analyze the utilization of electric vehicle charging infrastructure.

Its responsibilities include:

* managing charging infrastructure;
* monitoring charging usage;
* collecting operational telemetry;
* generating datasets;
* executing reproducible simulations;
* supporting Artificial Intelligence experiments;
* providing operational insights.

The platform intentionally does **not** control electrical energy delivery.

It observes charging operations without interfering in charging decisions.

This architectural boundary keeps the platform focused on experimentation and software engineering research.

---

# 4. Problem Statement

The growing adoption of electric vehicles increases demand for charging infrastructure.

Infrastructure operators must answer questions such as:

* Are charging stations being efficiently utilized?
* What are the busiest periods?
* How many connectors are typically occupied?
* How frequently are reservations cancelled?
* Can future occupancy be predicted?
* Is the existing infrastructure sufficient?

Answering these questions requires reliable operational data collected over time.

SCEP addresses this need by providing a platform capable of continuously observing charging infrastructure while supporting reproducible experimentation.

---

# 5. Ubiquitous Language

The following terminology shall be used consistently throughout the project.

Whenever a concept appears in source code, documentation, APIs or discussions, the definitions established here take precedence.

---

## Facility

A **Facility** represents the physical location where charging infrastructure is installed.

Examples include:

* residential condominiums;
* corporate buildings;
* shopping centers;
* university campuses;
* public parking facilities.

A Facility owns one or more Charging Stations.

---

## Charging Infrastructure

Charging Infrastructure represents the complete charging ecosystem belonging to a Facility.

It includes:

* charging stations;
* connectors;
* charging sessions;
* reservations;
* operational telemetry.

Charging Infrastructure is the primary object of observation within SCEP.

---

## Charging Station

A Charging Station represents a physical charging device installed inside a Facility.

A Charging Station:

* belongs to exactly one Facility;
* contains one or more Connectors;
* exposes operational status;
* participates in charging sessions.

The Charging Station is not reserved directly.

---

## Connector

A Connector represents an individual charging interface available to vehicles.

Examples include:

* CCS2;
* CHAdeMO;
* NACS;
* Type 2.

Reservations and Charging Sessions are associated with Connectors rather than Charging Stations.

This allows a single Charging Station to support multiple simultaneous charging sessions when multiple connectors are available.

---

## Vehicle

A Vehicle represents a physical or simulated electric vehicle owned by one authenticated
identity and capable of using the charging infrastructure.

One Human or Technical Client identity may own multiple Vehicles. Reservations and future
Charging Sessions reference Vehicle so that scheduling and operational history remain associated
with the actual physical or simulated participant.

One Vehicle shall not participate in overlapping Reservations.

SPEC-006 introduces Vehicle as a minimal supporting entity with identity, owner, display name,
status and timestamps. Advanced battery, power, compatibility, manufacturer, model and simulation
attributes are deferred.

The platform is not intended to become a vehicle management system.

---

## User

A User represents a person interacting with the charging infrastructure.

Users perform business activities such as:

* creating reservations;
* starting charging sessions;
* finishing charging sessions.

Authentication concerns are intentionally excluded from this definition.

A User is a business concept rather than a software account.

---

## Authenticated Identity

An Authenticated Identity is the account established by SPEC-005 for authorization and resource
ownership. It may be a Human account or a Technical Client account.

SPEC-006 uses Authenticated Identity, rather than the narrower business concept User, as the owner
of Vehicles and Reservations so simulated and human workflows follow the same domain rules.

---

## Reservation

A Reservation represents the intention to occupy a specific Connector during a future time window.

Reservations:

* belong to exactly one Connector;
* belong to exactly one authenticated identity;
* are assigned to exactly one Vehicle owned by that identity;
* may become a No-Show;
* may be cancelled;
* may result in a Charging Session.

A Reservation does not guarantee that charging will occur.

---

## Charging Session

A Charging Session represents the effective utilization of a Connector by a Vehicle.

A Charging Session begins when charging starts and ends when charging finishes.

Operational telemetry is associated with Charging Sessions.

Charging Sessions are the primary source of operational data.

---

## Telemetry

Telemetry represents operational measurements collected during Charging Sessions.

Examples include:

* charging power;
* accumulated energy;
* connector status;
* battery state of charge;
* charging duration.

Telemetry is always associated with a Charging Session.

It is never directly associated with a Facility or Charging Station.

---

## Domain Event

A Domain Event represents a business fact that has already occurred.

Examples include:

* ReservationCreated;
* ChargingSessionStarted;
* ChargingSessionFinished.

Domain Events provide the historical record required for analytics, observability and dataset generation.

---

## Simulation

A Simulation represents the execution of a reproducible experimental scenario.

Simulation produces synthetic business activity through the external Digital Twin Simulation Engine.

From the perspective of the Backend API, simulated users behave identically to real users.

---

## Prediction

A Prediction represents an estimation generated by an Artificial Intelligence model.

The initial prediction supported by SCEP is:

**Charging Infrastructure Occupancy Prediction**

Predictions estimate future utilization of charging infrastructure within a Facility.

---

## Experiment

An Experiment represents a reproducible research activity.

Experiments combine:

* simulation;
* operational data;
* datasets;
* AI models;
* evaluation metrics.

Experiments are first-class research artifacts.

---

# 6. Core Business Concepts

The domain revolves around a small number of central concepts.

```text id="huxbnt"
Facility

↓

Charging Infrastructure

↓

Charging Station

↓

Connector

↓

Reservation

↓

Charging Session

↓

Telemetry

↓

Analytics

↓

Prediction
```

This hierarchy represents the natural flow of operational information throughout the platform.

---

# 7. Domain Actors

The platform distinguishes business actors from software components.

Business actors represent real-world participants.

---

## Driver

Represents the person using the charging infrastructure.

Responsibilities include:

* creating reservations;
* initiating charging sessions;
* completing charging sessions.

---

## Facility Operator

Represents the organization responsible for operating the charging infrastructure.

Responsibilities include:

* monitoring utilization;
* managing charging stations;
* evaluating operational indicators.

---

## Platform Administrator

Responsible for platform configuration and administration.

Responsibilities include:

* system configuration;
* infrastructure management;
* operational supervision.

---

## Researcher

Responsible for conducting experiments using the platform.

Responsibilities include:

* executing simulations;
* generating datasets;
* evaluating architectural behavior.

---

## Data Scientist

Responsible for developing predictive models.

Responsibilities include:

* feature engineering;
* model training;
* prediction evaluation;
* experiment comparison.

---

# 8. Business Objectives

The platform pursues the following business objectives.

## Infrastructure Visibility

Provide complete visibility into charging infrastructure utilization.

---

## Operational Analysis

Transform charging activity into measurable operational indicators.

---

## Research Support

Provide a reproducible environment for Smart Charging experimentation.

---

## AI Readiness

Generate high-quality datasets suitable for machine learning.

---

## Architectural Evaluation

Provide a software platform suitable for evaluating modern Software Engineering practices.

---

# 9. Domain Principles

The following principles guide every business capability implemented by SCEP.

## Observe Before Controlling

SCEP observes charging infrastructure rather than controlling energy delivery.

---

## Infrastructure-Centric View

The platform manages charging infrastructure rather than electrical systems.

---

## Connector as the Operational Unit

Reservations and Charging Sessions occur at the Connector level.

Charging Stations provide physical grouping only.

---

## Business First

Operational workflows take precedence over analytical concerns.

Analytics are derived from business activity rather than driving it.

---

## Research by Design

Every operational activity should produce information valuable for experimentation and scientific analysis.

---

# 10. Relationship with Other Specifications

This specification establishes the vocabulary adopted by every subsequent specification.

Future documents shall specialize the concepts introduced here without redefining them.

In case of terminology conflicts, the definitions established in this document take precedence.

This specification therefore becomes the authoritative business dictionary of the Smart Charging Experimentation Platform.

---

# 11. Domain Model

The Smart Charging domain is centered around the utilization of charging infrastructure.

The conceptual model is illustrated below.

```text
Facility
    └── owns ──► Charging Station
                     └── contains ──► Connector ◄── reserves ── Reservation
                                                                       ▲
Identity ── owns ──► Vehicle ◄──────────── assigned to ────────────────┘
    │                  │
    └── creates ───────┘

Reservation ── may originate ──► Charging Session
                                      └── generates ──► Telemetry
                                                               │
                                                               ▼
Domain Events ── feed ──► Analytics ──► Dataset Export ──► Prediction
```

The model intentionally represents the natural lifecycle of charging infrastructure utilization.

Business information always flows from operational activities toward analytical capabilities.

---

# 12. Aggregates

The domain is organized into Aggregates following Domain-Driven Design principles.

Each Aggregate owns its own consistency boundary.

---

## Facility Aggregate

Root Entity:

* Facility

Responsibilities:

* own charging infrastructure;
* provide organizational context;
* aggregate operational indicators.

Owned Entities:

* Charging Station.

---

## Charging Station Aggregate

Root Entity:

* Charging Station

Responsibilities:

* represent physical charging equipment;
* expose operational status;
* manage available connectors.

Owned Entities:

* Connector.

---

## Reservation Aggregate

Root Entity:

* Reservation

Responsibilities:

* reserve connector usage;
* validate reservation rules;
* manage reservation lifecycle.

Associated Entities:

* authenticated Identity;
* Vehicle;
* Connector.

---

## Charging Session Aggregate

Root Entity:

* Charging Session

Responsibilities:

* represent effective connector utilization;
* own operational telemetry;
* calculate charging duration.

Owned Entities:

* Telemetry Records.

Associated Entities:

* Vehicle;
* Connector;
* authenticated Identity.

---

## Prediction Aggregate

Root Entity:

* Prediction

Responsibilities:

* represent AI prediction results;
* preserve prediction history;
* support analytical comparison.

---

# 13. Entities

The following business entities exist within the domain.

---

## Facility

Identity:

* Facility ID

Mutable:

Yes.

Examples:

* Shopping Center
* University Campus
* Residential Condominium
* Corporate Parking Facility

---

## Charging Station

Identity:

* Station ID

Characteristics:

* physical device;
* belongs to one Facility;
* contains one or more Connectors.

---

## Connector

Identity:

* Connector ID

Characteristics:

* physical charging interface;
* independently reservable;
* independently occupied.

The Connector is the smallest operational unit within the domain.

---

## User

Identity:

* User ID

Represents a person using the charging infrastructure.

Authentication details are outside the domain model.

---

## Vehicle

Identity:

* Vehicle ID

Represents a physical or simulated electric vehicle owned by one authenticated identity and
participating in Reservations and future Charging Sessions.

Vehicle is a supporting entity introduced by SPEC-006, not a separate Aggregate in the current
model. Its minimal lifecycle is ACTIVE or INACTIVE. Only ACTIVE Vehicles may receive new
Reservations, while INACTIVE Vehicles remain referenced by history.

Future versions may include additional characteristics such as:

* battery capacity;
* connector compatibility;
* charging power.

---

## Reservation

Identity:

* Reservation ID

Represents a future allocation of connector usage.

---

## Charging Session

Identity:

* Session ID

Represents actual connector utilization.

This is the primary operational entity of the platform.

---

## Telemetry Record

Identity:

* Telemetry Record ID

Represents an individual operational measurement.

Telemetry records always belong to a Charging Session.

---

## Prediction

Identity:

* Prediction ID

Represents an AI-generated prediction.

---

# 14. Value Objects

The following concepts are modeled as Value Objects.

---

## Time Window

Represents:

* reservation interval;
* charging interval;
* experiment interval.

Immutable.

---

## Location

Represents the physical location of a Facility.

Examples:

* address;
* coordinates.

---

## Connector Type

Examples:

* CCS2;
* CHAdeMO;
* NACS;
* Type 2.

Immutable.

---

## Energy

Represents delivered electrical energy.

Examples:

* kWh.

---

## Power

Represents instantaneous charging power.

Examples:

* kW.

---

## Occupancy Rate

Represents charging infrastructure utilization.

Examples:

* 25%
* 50%
* 80%

This Value Object is central to analytical capabilities.

---

# 15. Relationships

The domain relationships are summarized below.

| Source           | Relationship    | Target           |
| ---------------- | --------------- | ---------------- |
| Facility         | owns            | Charging Station |
| Charging Station | contains        | Connector        |
| Identity         | owns            | Vehicle          |
| Identity         | creates         | Reservation      |
| Reservation      | assigned to     | Vehicle          |
| Reservation      | reserves        | Connector        |
| Reservation      | may originate   | Charging Session |
| Identity         | starts          | Charging Session |
| Vehicle          | participates in | Charging Session |
| Charging Session | uses            | Connector        |
| Charging Session | generates       | Telemetry        |
| Charging Session | publishes       | Domain Events    |
| Analytics        | consumes        | Domain Events    |
| Dataset Export   | consumes        | Domain Events    |
| Prediction       | consumes        | Datasets         |

---

# 16. Domain Ownership

Every business concept has a single owner.

Ownership guarantees consistency and avoids ambiguous responsibilities.

| Aggregate        | Owns                  |
| ---------------- | --------------------- |
| Facility         | Charging Stations     |
| Charging Station | Connectors            |
| Reservation      | Reservation lifecycle |
| Charging Session | Telemetry             |
| Prediction       | Prediction results    |

Vehicle is a supporting entity owned by the Smart Charging capability introduced in SPEC-006.
It is not a separate Aggregate in the current domain model.

No Aggregate shall modify entities owned by another Aggregate directly.

Communication shall occur through:

* application services;
* Domain Events.

---

# 17. Lifecycle Overview

The complete operational lifecycle follows the sequence below.

```text
Facility

↓

Charging Station

↓

Connector

↓

Reservation

↓

Charging Session

↓

Telemetry

↓

Domain Events

↓

Analytics

↓

Dataset Export

↓

Prediction
```

This lifecycle is intentionally linear.

Business activity always precedes analytical processing.

Artificial Intelligence never becomes the source of operational truth.

---

# 18. Bounded Context

Within the current scope, SCEP consists of a single Bounded Context.

```text
Smart Charging Experimentation Platform

┌─────────────────────────────────────┐

Facility

Charging Infrastructure

Reservations

Charging Sessions

Telemetry

Analytics

Prediction

└─────────────────────────────────────┘
```

Although internal modules exist, they belong to the same business context and therefore share a common ubiquitous language.

Future versions may introduce additional Bounded Contexts if new business domains emerge.

---

# 19. Domain Invariants

The following invariants shall always hold true.

* Every Charging Station belongs to exactly one Facility.
* Every Connector belongs to exactly one Charging Station.
* Every Reservation belongs to exactly one Connector.
* Every Reservation is assigned to exactly one Vehicle.
* Every Vehicle belongs to exactly one authenticated identity.
* Every Reservation owner is the owner of its assigned Vehicle.
* One Vehicle cannot participate in overlapping blocking Reservations.
* Every Charging Session uses exactly one Connector.
* Every Charging Session belongs to one User.
* Every Telemetry Record belongs to one Charging Session.
* Every Prediction references a single experiment or operational dataset.
* Operational truth always originates from business activity.

Violating these invariants constitutes a domain error rather than an implementation error.

---

# 20. Business Rules

The following business rules define the expected behavior of the Smart Charging domain.

Detailed implementation rules will be specified in subsequent functional specifications.

---

## BR-001 — Facility Ownership

Every Charging Station shall belong to exactly one Facility.

A Charging Station cannot exist independently.

---

## BR-002 — Connector Ownership

Every Connector shall belong to exactly one Charging Station.

A Connector cannot be shared between Charging Stations.

---

## BR-003 — Reservation Target

Reservations shall always be associated with a Connector.

Charging Stations are never reserved directly.

---

## BR-004 — Connector Availability

A Connector may participate in only one active Charging Session at any given time.

Future Reservations block the Connector calendar according to SPEC-006 but do not constitute
active charging occupation.

---

## BR-005 — Reservation No-Show

A CONFIRMED Reservation becomes NO_SHOW after its configured Grace Period when no Charging
Session has activated it.

NO_SHOW Reservations release Connector and Vehicle calendars automatically and remain historical.

---

## BR-006 — Charging Session Creation

A Charging Session may begin:

* from an existing Reservation; or
* directly, when the Connector is available.

This allows the platform to support both reservation-based and walk-in charging.

---

## BR-007 — Telemetry Association

Every Telemetry Record shall belong to exactly one Charging Session.

Telemetry shall never be associated directly with:

* Facilities;
* Charging Stations;
* Connectors.

---

## BR-008 — Operational Truth

Operational state is determined exclusively by business transactions.

Analytics, datasets and predictions are derived artifacts and shall never modify operational data.

---

## BR-009 — Prediction Independence

Predictions shall never influence operational workflows.

Prediction results are advisory and intended to support analysis and decision-making.

---

## BR-010 — Simulation Equivalence

From the perspective of the Backend API, simulated users and real users shall be processed identically.

Business rules shall not distinguish between simulation-generated requests and operational requests.

---

# 21. Connector Lifecycle

The Connector is the primary operational resource within the platform.

Its lifecycle is intentionally simple.

```text id="i7m6mb"
Available

    │

    ├────────────── Reservation ──────────────┐

    ▼                                         │

Reserved                                      │

    │                                         │

    ├──────────── Charging Starts ────────────┐

    ▼                                         │

Charging                                     │

    │                                         │

    ├──────────── Charging Ends ──────────────┐

    ▼                                         │

Available
```

Exceptional situations include:

* OutOfService;
* Maintenance.

These states are administrative and suspend normal business operations.

---

# 22. Reservation Lifecycle

Reservations follow the lifecycle below.

```text id="trvjlwm"
CONFIRMED ──► ACTIVE ──► COMPLETED
    │
    ├────────► CANCELLED
    ├────────► LATE_CANCELLED
    └────────► NO_SHOW
```

Only CONFIRMED and ACTIVE Reservations block Connector and Vehicle calendars. Terminal statuses
remain historical and do not block future Reservations. Detailed interval, cancellation,
rescheduling and activation rules are defined by SPEC-006.

Every transition generates a Domain Event.

---

# 23. Charging Session Lifecycle

Charging Sessions represent the effective utilization of charging infrastructure.

Lifecycle:

```text id="5v9o7p"
Started

    │

    ▼

Charging

    │

    ▼

Completed
```

Possible interruptions:

* Paused (future enhancement);
* Failed (future enhancement).

The MVP considers only successful completion.

---

# 24. Domain Events Overview

Business activity generates immutable Domain Events.

Examples include:

Reservation

* ReservationCreated
* ReservationCancelled
* ReservationLateCancelled
* ReservationNoShow

Charging

* ChargingSessionStarted
* ChargingSessionFinished

Infrastructure

* ConnectorOccupied
* ConnectorReleased
* StationUnavailable
* StationAvailable

Telemetry

* TelemetryRecorded

Analytics

* DatasetExported
* PredictionGenerated

These events establish the historical record required for research and observability.

---

# 25. Key Performance Indicator

The primary business indicator of SCEP is:

## Charging Occupancy Rate

Definition:

The percentage of available Connectors that are actively occupied during a given observation period.

Conceptually:

```text id="r4y3up"
Occupied Connectors

──────────────────────────────

Available Connectors
```

This KPI serves as the foundation for:

* dashboards;
* operational analytics;
* dataset generation;
* prediction models.

Future KPIs shall complement, rather than replace, this indicator.

---

# 26. Domain Assumptions

The following assumptions define the scope of the platform.

SCEP assumes that:

* charging infrastructure already exists;
* charging hardware operates correctly;
* energy delivery is managed externally;
* communication with chargers occurs through external systems or future integrations;
* users behave according to realistic operational scenarios.

The platform deliberately excludes electrical control algorithms.

---

# 27. Out of Scope

The following concerns are intentionally excluded from the current domain.

* electrical energy optimization;
* smart grid coordination;
* payment processing;
* billing;
* energy market participation;
* charger firmware management;
* hardware diagnostics;
* battery chemistry analysis;
* vehicle navigation;
* route planning.

These topics may be explored in future research but are not part of the current project.

---

# 28. Relationship with Artificial Intelligence

Artificial Intelligence is a consumer of operational knowledge.

The domain produces:

* reservations;
* charging sessions;
* telemetry;
* domain events.

These artifacts are transformed into:

* datasets;
* features;
* predictive models.

The direction of information is always:

```text id="owh4mv"
Business Activity

↓

Operational Data

↓

Analytics

↓

Datasets

↓

Artificial Intelligence

↓

Predictions
```

Artificial Intelligence never becomes the source of business truth.

---

# 29. Acceptance Criteria

This specification is considered complete when:

* the business vocabulary is unambiguous;
* all core concepts are defined;
* entity relationships are documented;
* aggregate boundaries are established;
* business invariants are identified;
* operational lifecycle is documented;
* business rules are defined at a conceptual level;
* future specifications can reference this document without redefining terminology.

---

# 30. Relationship with Other Specifications

This specification provides the conceptual foundation for:

* SPEC-003 — Facilities
* SPEC-004 — Charging Stations
* SPEC-005 — Identity and Access
* SPEC-006 — Reservations, including the minimal Vehicle capability
* SPEC-007 — Charging Sessions
* SPEC-008 — Telemetry
* SPEC-009 — Domain Events
* SPEC-010 — Analytics
* SPEC-011 — Dataset Export
* SPEC-012 — Predictions
* SPEC-013 — Digital Twin Simulation Engine

All future specifications shall inherit the ubiquitous language defined here.

---

# 31. Final Considerations

This document establishes the **Ubiquitous Language** of the Smart Charging Experimentation Platform.

Rather than describing software implementation, it defines the conceptual model shared by developers, researchers and stakeholders.

By distinguishing operational truth from analytical artifacts, separating infrastructure management from electrical control and treating charging infrastructure utilization as the central business concern, this specification provides a stable conceptual foundation for the remainder of the project.

Every subsequent specification, architectural decision and implementation shall preserve the terminology, relationships and business principles established herein.

The Domain Model defined in this document is therefore considered the authoritative business reference for SCEP.
