# Functional Specifications

This directory contains the functional specifications of the **Smart Charging Experimentation Platform (SCEP)**.

Unlike the Architecture Specifications, which describe **how the platform is organized**, these documents define **what the platform must do** and serve as the implementation contract for each development iteration.

Every software feature should be implemented only after its corresponding specification has been approved.

---

# Development Process

SCEP follows a **Specification-Driven Development** process.

```text
Architecture

↓

Architecture Decision Records (ADRs)

↓

Functional Specifications

↓

Implementation

↓

Testing

↓

Code Review

↓

Release
```

Architecture establishes the technical foundation.

ADRs document architectural decisions.

Functional Specifications describe business capabilities.

Implementation becomes the translation of approved specifications into software.

---

# Specification Status

| ID | Specification | Document Status | Implementation Status |
|---|---|---|---|
| SPEC-001 | Project Foundation | Approved | Implemented |
| SPEC-002 | Domain Model and Ubiquitous Language | Approved | Implemented |
| SPEC-003 | Facilities | Approved | Implemented |
| SPEC-004 | Charging Stations | Approved | Implemented |
| SPEC-005 | Identity and Access | Approved | Implemented |
| SPEC-006 | Reservations | Approved | Implemented |
| SPEC-007 | Charging Sessions | Approved | Implemented |
| SPEC-008 | Smart Charging Domain Telemetry | Approved | Implemented |
| SPEC-009 | Domain Events | Approved | Implemented |
| SPEC-010 | Analytics | Approved | Implemented |
| SPEC-011 | Dataset Export | Approved | Implemented |
| SPEC-012 | Weekly Occupancy Predictions | Draft / Under Review | Planned |
| SPEC-013 | Digital Twin Simulation Engine | Planned | Not Implemented |

---

# Specification Dependencies

Specifications should be implemented in the following order.

```text
SPEC-001
Project Foundation

↓

SPEC-002
Domain Model & Ubiquitous Language

↓

SPEC-003
Facilities

↓

SPEC-004
Charging Stations

↓

SPEC-005
Identity & Access

↓

SPEC-006
Reservations

↓

SPEC-007
Charging Sessions

↓

SPEC-008
Smart Charging Domain Telemetry

↓

SPEC-009
Domain Events

↓

SPEC-010
Analytics

↓

SPEC-011
Dataset Export

↓

SPEC-013
Digital Twin Simulation Engine

↓

SPEC-012
Weekly Occupancy Predictions
```

The sequence follows the natural evolution of the domain.

Infrastructure is established first, followed by the domain model, operational entities and finally analytical and AI capabilities.

SPEC-013 precedes SPEC-012 in the recommended implementation sequence so representative synthetic
data can support the first occupancy experiment. This ordering does not create a mandatory runtime
dependency from Predictions to the Simulation Engine.

---

# Specification Responsibilities

## SPEC-001 — Project Foundation

Establishes the technical foundation of the platform.

Topics include:

* project structure;
* development environment;
* Docker Compose;
* PostgreSQL;
* observability foundation;
* CI/CD foundation;
* quality tooling.

---

## SPEC-002 — Domain Model and Ubiquitous Language

Defines the business language of SCEP.

Topics include:

* ubiquitous language;
* domain concepts;
* aggregates;
* entities;
* value objects;
* business rules;
* domain relationships.

This document serves as the business dictionary of the platform.

---

## SPEC-003 — Facilities

Defines the Facility Aggregate.

Topics include:

* operational environments;
* facility lifecycle;
* operating hours;
* facility types;
* ownership boundaries;
* analytical context.

Facilities represent the root operational context of the Smart Charging domain.

---

## SPEC-004 — Charging Stations

Defines charging infrastructure.

Topics include:

* charging stations;
* connectors;
* infrastructure lifecycle;
* operational status;
* REST APIs;
* persistence model;
* domain events.

---

## SPEC-005 — Identity and Access

Defines authentication and authorization.

Topics include:

* users;
* roles;
* permissions;
* JWT authentication;
* access control.

---

## SPEC-006 — Reservations

Defines reservation workflows and introduces the minimum Vehicle capability required for
scheduling.

Topics include:

* Vehicle ownership and lifecycle;
* reservation lifecycle;
* Connector and Vehicle overlap validation;
* rescheduling, cancellation and no-show processing;
* cancellation;
* Vehicle and Reservation APIs.

---

## SPEC-007 — Charging Sessions

Defines charging execution.

Topics include:

* charging lifecycle;
* activation from exactly one Reservation;
* Connector and Vehicle exclusivity;
* session completion.

---

## SPEC-008 — Smart Charging Domain Telemetry

Defines telemetry ingestion.

Topics include:

* measurements;
* charging metrics;
* sensor data;
* telemetry validation;
* ingestion APIs.

SPEC-008 is approved and implemented.

---

## SPEC-009 — Domain Events

Defines the business event model.

Topics include:

* event contracts;
* publication;
* consumption;
* event versioning.

SPEC-009 is implemented with a transactional PostgreSQL Event Store and internal dispatcher.

---

## SPEC-010 — Analytics

Defines analytical capabilities.

Topics include:

* KPIs;
* read-only analytical queries;
* occupancy metrics;
* Reservation, Charging Session and energy metrics;
* time-series aggregation.

SPEC-010 is approved and implemented with read-only, on-demand analytical projections.

---

## SPEC-011 — Dataset Export

Defines research dataset generation.

Topics include:

* dataset generation;
* metadata;
* export formats;
* reproducibility.

---

## SPEC-012 — Weekly Occupancy Predictions

Defines controlled publication and consumption of externally generated recurring weekly occupancy
profiles.

Topics include:

* immutable 168-bucket publications;
* Facility, Station and Connector scopes;
* SPEC-010 `effective_occupancy_rate` prediction;
* Dataset Export provenance;
* point lookup and EVDriver Connector recommendations;
* authorized external AI publication.

SPEC-012 is Draft / Under Review and Planned. Its recommended implementation sequence is after
SPEC-013, although it has no mandatory runtime dependency on the Simulation Engine.

---

## SPEC-013 — Digital Twin Simulation Engine

Defines the external simulation platform.

Topics include:

* simulation scenarios;
* synthetic users;
* synthetic vehicles;
* synthetic charging infrastructure usage;
* deterministic experiments.

---

# Relationship with Architecture

Every Functional Specification must remain consistent with:

* Architecture Specifications;
* Architecture Decision Records (ADRs).

Whenever a Functional Specification requires a new architectural decision, a new ADR should be created before implementation.

---

# Definition of Done

A specification is considered complete when:

* its scope is clearly defined;
* business rules are documented;
* REST contracts are defined (when applicable);
* persistence model is defined (when applicable);
* acceptance criteria are documented;
* implementation can proceed without major architectural decisions.

---

# Current Project Status

Current milestone:

**Specification Baseline v1.1**

Completed:

* ✅ Architecture Specifications
* ✅ Architecture Decision Records
* ✅ Project Foundation
* ✅ Domain Model and Ubiquitous Language
* ✅ Facilities
* ✅ Charging Stations
* ✅ Identity and Access implementation
* ✅ Vehicles and Reservations implementation
* ✅ Charging Sessions implementation
* ✅ Telemetry implementation
* ✅ Domain Events implementation
* ✅ Analytics implementation
* ✅ Dataset Export implementation

SPEC-001 through SPEC-011 are approved and implemented. SPEC-012 is Draft / Under Review and
Planned. SPEC-013 remains Planned and not implemented. Neither SPEC-012 nor SPEC-013 is implemented.
