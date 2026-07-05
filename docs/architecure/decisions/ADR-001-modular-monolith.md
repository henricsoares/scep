# ADR-001 — Adopt Modular Monolith Architecture

**Status:** Accepted
**Date:** 2026
**Related Specs:**

* `001-architecture-vision.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`
* `006-quality-attributes.md`

---

# Context

The Smart Charging Experimentation Platform (SCEP) is a research-oriented platform designed to support experimentation in Smart Charging, synthetic data generation, observability and AI-based analysis.

The platform must support multiple business and research capabilities, including:

* Smart Charging domain workflows;
* telemetry ingestion;
* event persistence;
* analytics;
* dataset export;
* AI experimentation;
* observability;
* DevSecOps.

Although these responsibilities are distinct, the project is developed in an academic context with limited implementation time and a small development team.

Therefore, the architecture must balance modularity and simplicity.

---

# Decision

The Backend API container of SCEP will adopt a Modular Monolith architecture.

Other platform containers, including the Web Application, Digital Twin Simulation Engine, AI Research Environment and Observability Stack, remain independent applications as defined in the container architecture.

The system will be deployed as a single backend application, but internally organized into explicit modules with clear responsibilities and boundaries.

Initial modules include:

* Identity and Access;
* Smart Charging;
* Telemetry;
* Domain Events;
* Analytics;
* Dataset Export;
* Prediction;
* Notification;
* Observability.

---

# Rationale

A Modular Monolith provides the benefits of modular design without the operational complexity of distributed microservices.

This decision supports the following quality attributes:

* maintainability;
* testability;
* reproducibility;
* observability;
* extensibility;
* development simplicity.

The architecture allows the project to demonstrate modern Software Engineering principles while remaining feasible within the scope of a postgraduate final project.

---

# Alternatives Considered

## Traditional Monolith

A traditional monolith would be simpler to implement initially, but it would likely lead to strong coupling between unrelated concerns such as charging rules, analytics, datasets and predictions.

Rejected because it does not sufficiently support architectural clarity or long-term evolution.

---

## Microservices

Microservices would provide strong deployment independence and scalability.

However, they would introduce additional complexity:

* distributed communication;
* service discovery;
* deployment orchestration;
* distributed tracing;
* data consistency challenges;
* increased DevOps overhead.

Rejected because the project does not require independent deployment of services at this stage.

---

## Modular Monolith

Selected because it provides a strong balance between simplicity and architectural discipline.

It allows internal separation of concerns while preserving a single deployment unit.

---

# Consequences

## Positive Consequences

* simpler local development;
* simpler deployment;
* easier debugging;
* lower infrastructure cost;
* clear module boundaries;
* easier automated testing;
* easier onboarding;
* future migration path to microservices if needed.

---

## Negative Consequences

* modules cannot be independently deployed;
* runtime scalability is limited to the backend application as a whole;
* architectural discipline must be actively maintained;
* poor implementation may degrade into a traditional monolith.

---

# Architectural Rules

The following rules must be respected:

* each module owns its domain logic;
* each module owns its persistence access;
* modules must not directly access another module's internal implementation;
* cross-module communication should occur through explicit interfaces or domain events;
* API controllers must not contain business rules;
* analytics and AI components must not modify transactional business state;
* architecture tests should be introduced to prevent dependency violations.

---

# Future Evolution

The Simulation Engine is intentionally **not** part of the Modular Monolith.

It is implemented as an independent application that interacts with SCEP exclusively through public APIs.

This separation was adopted to ensure that simulated clients and future real-world charging infrastructure are treated identically by the platform.

If future scalability requirements arise, internal backend modules may be extracted into independent services.

Potential extraction candidates include:

- Telemetry Component;
- Analytics Component;
- Dataset Export Component;
- Prediction Component.

The Smart Charging domain should remain the core of the Backend API for as long as the platform is developed as a Modular Monolith.

---

# Decision Outcome

The Backend API will be implemented as a **Python FastAPI Modular Monolith**, using explicit internal modules and event-driven communication where appropriate.

This architecture is considered the baseline for all future backend implementation and specification work.
