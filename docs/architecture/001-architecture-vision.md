# Architecture View 001 — Architecture Vision

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

**Version:** 2.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

## Vision

The **Smart Charging Experimentation Platform (SCEP)** is an open, modular and extensible software platform designed to support research, experimentation and validation of solutions for intelligent electric vehicle charging infrastructures.

Unlike commercial charging management systems, the primary objective of SCEP is not simply to operate charging stations, but to provide a reproducible environment where modern Software Engineering practices, Internet of Things (IoT), Data Engineering and Artificial Intelligence can be integrated and experimentally evaluated.

The platform combines a realistic business domain with software architecture best practices, enabling the execution of controlled experiments, generation of synthetic datasets, collection of operational metrics and validation of predictive models.

Electric vehicle charging management represents the first application domain implemented on the platform, serving as a realistic case study for experimentation and future research.

---

## Mission

Develop a modern experimentation platform capable of supporting the complete lifecycle of Smart Charging research, from data generation to predictive analytics, while demonstrating the practical application of modern Software Engineering principles.

---

## Vision Statement

To become a reusable reference platform for experimentation in Smart Charging systems, enabling researchers and software engineers to evaluate architectures, algorithms and intelligent services without requiring physical charging infrastructure.

---

# 2. Motivation

The worldwide adoption of electric vehicles continues to increase, creating new challenges for organizations responsible for shared charging infrastructures such as residential condominiums, universities, corporate campuses and public parking facilities.

Managing these environments involves considerably more than simply reserving charging stations.

Operators must deal with problems such as:

- competition for limited charging resources;
- demand peaks;
- unpredictable occupancy;
- inefficient charger utilization;
- lack of operational visibility;
- absence of historical data;
- difficulty validating scheduling strategies;
- lack of datasets for AI research.

While numerous commercial charging management systems already exist, they generally focus on operational functionality and rarely expose mechanisms that support scientific experimentation or architectural evaluation.

Similarly, researchers interested in Smart Charging frequently face a lack of realistic datasets and reproducible environments for validating new approaches.

These limitations motivated the development of SCEP.

Instead of proposing yet another charging management application, this project proposes an experimentation platform capable of reproducing realistic operational scenarios and generating high-quality synthetic datasets suitable for software engineering research.

---

# 3. Research Problem

Current Smart Charging research presents several practical limitations.

Real charging infrastructure is expensive.

Operational data is usually private.

Public datasets are scarce.

Deploying experimental software in production environments is generally impractical.

Consequently, researchers frequently validate their ideas using simplified simulations that poorly represent real operational environments.

This work addresses the following research question:

> **How can a modern software platform be designed to support reproducible experimentation, synthetic data generation and intelligent services for Smart Charging while adopting contemporary Software Engineering practices?**

---

# 4. Expected Contributions

Rather than delivering only a software product, this project aims to contribute an extensible research platform.

Expected contributions include:

- a reference architecture for Smart Charging experimentation;
- an event-driven modular software platform;
- a configurable simulation environment;
- automatic generation of realistic operational datasets;
- integrated observability infrastructure;
- a reproducible development environment;
- a foundation for AI-based experiments;
- an open platform suitable for future academic research.

The charging management system itself should be understood as the first demonstration of the platform's capabilities.

---

# 5. Project Objectives

## General Objective

Develop a Smart Charging experimentation platform capable of integrating software engineering, simulation, analytics and artificial intelligence into a single reproducible environment.

---

## Software Engineering Objectives

- demonstrate Modular Monolith architecture;
- apply Domain-Driven Design concepts;
- adopt Event-Driven Architecture;
- implement DevSecOps practices;
- implement complete observability;
- ensure high software quality through automated testing;
- provide reproducible infrastructure.

---

## Research Objectives

- generate realistic synthetic datasets;
- support reproducible experiments;
- evaluate software architecture decisions;
- evaluate operational metrics;
- support AI model development;
- enable future comparative studies.

---

## Business Objectives

The platform shall support:

- user management;
- charging station management;
- reservation management;
- charging session management;
- charger occupancy monitoring;
- telemetry collection;
- operational dashboards;
- prediction of charger occupancy.

---

# 6. Scope

## Included

The first version of the platform includes:

- Web API;
- Web application;
- authentication and authorization;
- charging station management;
- reservation system;
- charging session lifecycle;
- telemetry ingestion;
- simulation engine;
- operational analytics;
- AI experimentation support;
- observability infrastructure;
- CI/CD pipeline;
- infrastructure as code using containers.

---

## Explicitly Out of Scope

The following features are intentionally excluded from this project:

- payment processing;
- billing systems;
- mobile applications;
- integration with commercial charging networks;
- OCPP communication with physical chargers;
- energy market integration;
- Vehicle-to-Grid (V2G);
- production-scale distributed deployment.

These features may become future research topics.

---

# 7. Architectural Drivers

The architecture of SCEP is guided by quality attributes rather than technology choices.

The following drivers influenced every architectural decision.

## Modularity

Business domains must evolve independently while remaining deployable as a single application.

---

## Maintainability

The project must remain understandable and extensible throughout the entire research lifecycle.

---

## Testability

Every architectural decision should facilitate automated testing.

---

## Observability

The platform must expose sufficient operational data to understand both business behavior and software behavior.

Observability is considered part of the research object rather than merely an operational concern.

---

## Reproducibility

Every experiment executed using the platform must be reproducible.

This includes:

- simulation parameters;
- datasets;
- infrastructure;
- software versions.

---

## Extensibility

New business domains, simulators and AI models should be incorporable with minimal architectural changes.

---

## Research Orientation

Architectural decisions should prioritize experimentation over production optimization.

Whenever a trade-off exists between simplicity and experimental flexibility, preference should be given to the latter.

---

# 8. Architectural Vision

SCEP adopts a **Modular Monolith** architecture combined with **Event-Driven communication** between business modules.

This approach was selected because it offers an excellent balance between architectural quality and operational simplicity.

The platform behaves as a single deployable application while internally preserving clear module boundaries and loose coupling.

Every important business action produces a domain event.

These events become the foundation for:

- analytics;
- observability;
- dashboards;
- simulation;
- dataset generation;
- AI model training.

Instead of treating analytics and machine learning as external concerns, SCEP considers them first-class architectural citizens.

The architecture is intentionally designed so that operational execution continuously generates research assets.

Every reservation, charging session, telemetry update and simulation contributes to the production of datasets that may later be consumed by analytical and predictive components.

In this sense, the platform simultaneously behaves as:

- an operational management system;
- an event producer;
- a data generation platform;
- an experimentation laboratory.

---

# 9. Architectural Principles

The platform follows the principles below throughout its implementation.

## Domain-Driven Design

Business complexity is organized into independent domains with explicit responsibilities and bounded contexts.

---

## Event-Driven Architecture

Business events represent immutable facts.

Whenever possible, communication between modules occurs through domain events rather than direct dependencies.

---

## Clean Architecture

Business rules remain independent from frameworks, infrastructure and external services.

---

## API First

All business capabilities are exposed through well-defined APIs, enabling future integrations and automation.

---

## Observability by Design

Logging, metrics and distributed tracing are considered mandatory architectural capabilities rather than operational add-ons.

---

## Security by Design

Authentication, authorization, dependency management and secure development practices are incorporated from the beginning of the project.

---

## Experimentation by Design

The platform is intentionally designed to support experimentation.

Simulation, dataset generation and reproducibility are architectural capabilities and not auxiliary features.

Every major subsystem should contribute, directly or indirectly, to the platform's research objectives.

# 10. Platform Overview

SCEP is organized as a collection of cohesive business modules executing within a single application process.

Each module encapsulates its own business rules, application services, persistence layer and domain events.

Communication between modules should occur through explicit contracts or domain events, avoiding direct knowledge of internal implementations.

The platform is logically divided into four major layers:

- Platform Core
- Business Domain
- Research Services
- Cross-Cutting Services

---

# 11. Platform Modules

## 11.1 Platform Core

The Platform Core provides common services shared by every other module.

Responsibilities include:

- authentication;
- authorization;
- user management;
- role management;
- audit information;
- configuration management;
- API infrastructure.

The Core contains no Smart Charging business logic.

Its purpose is to provide reusable platform capabilities.

---

## 11.2 Smart Charging Domain

The Smart Charging Domain represents the primary business context implemented by the platform.

It models the operational lifecycle of shared charging infrastructure.

Its responsibilities include:

- charging station registration;
- charger availability;
- reservation lifecycle;
- charging session lifecycle;
- occupancy management;
- business rules;
- conflict resolution.

This domain represents the first experimental scenario supported by SCEP and serves as the reference implementation for future domains.

---

## 11.3 Telemetry

The Telemetry module is responsible for ingesting operational events generated by charging stations or simulated devices.

Typical telemetry includes:

- charging power;
- delivered energy;
- voltage;
- current;
- connector status;
- charger temperature;
- session duration;
- battery state of charge (SoC).

Telemetry data should be normalized before becoming available to other modules.

The module is intentionally independent from physical communication protocols, allowing simulated and real devices to coexist behind the same interface.

---

## 11.4 Simulation Engine

The Simulation Engine is one of the core components of the platform.

Rather than acting as a simple mock generator, it provides a configurable digital environment capable of reproducing realistic charging scenarios.

The simulator exists to solve one of the main research problems addressed by this project:

> the lack of large, high-quality datasets for Smart Charging research.

Simulation scenarios may include:

- users;
- vehicles;
- charging stations;
- reservations;
- charging sessions;
- cancellations;
- no-shows;
- equipment failures;
- maintenance windows;
- occupancy peaks;
- seasonal behavior;
- weather influence;
- stochastic events.

Simulation execution must be deterministic whenever a seed is provided, allowing experiments to be reproduced.

Every simulation execution becomes part of the platform's historical dataset.

---

## 11.5 Analytics

The Analytics module transforms operational events into business information.

Responsibilities include:

- KPI calculation;
- occupancy statistics;
- utilization analysis;
- historical reports;
- operational dashboards;
- dataset aggregation.

Analytics must consume business events without interfering with operational modules.

This separation allows new analytical capabilities to be introduced without modifying the business domain.

---

## 11.6 AI Experimentation

The AI Experimentation module consumes historical datasets generated by the platform.

Its purpose is not to provide production-grade artificial intelligence services, but to support reproducible research.

The first supported experiment is:

- charger occupancy prediction.

Future experiments may include:

- charging demand forecasting;
- anomaly detection;
- predictive maintenance;
- charging recommendation;
- scheduling optimization;
- energy optimization.

AI models remain isolated from operational business rules.

The platform produces data.

The AI module consumes data.

This separation preserves architectural independence.

---

## 11.7 Observability

Observability is treated as a first-class architectural capability.

Rather than existing solely for operational monitoring, observability data also supports architectural evaluation and research.

Responsibilities include:

- structured logging;
- metrics collection;
- distributed tracing;
- health monitoring;
- performance visualization.

Every module is expected to expose sufficient telemetry to allow complete understanding of its runtime behavior.

---

# 12. Architectural Flow

The platform continuously transforms operational activity into research assets.

The simplified execution flow is described below.

```text
User / Simulator

        │

        ▼

Business Operation

        │

        ▼

Domain Event

        │

        ▼

Persistent Storage

        │

        ▼

Analytics Pipeline

        │

        ▼

Research Dataset

        │

        ▼

Machine Learning

        │

        ▼

Predictions & Dashboards
```

Unlike conventional enterprise systems, data generation is not considered a secondary effect of business execution.

It is one of the primary architectural objectives.

---

# 13. Domain Events

Events represent immutable facts that occurred within the business domain.

Every significant business operation shall publish at least one domain event.

Events are used by:

- Analytics;
- Observability;
- Simulation;
- AI;
- auditing;
- future integrations.

Initial domain events include:

### Reservation Events

- ReservationCreated
- ReservationConfirmed
- ReservationCancelled
- ReservationLateCancelled
- ReservationNoShow

### Charging Events

- ChargingSessionStarted
- ChargingSessionPaused
- ChargingSessionResumed
- ChargingSessionFinished

### Vehicle Events

- VehicleConnected
- VehicleDisconnected

### Station Events

- StationOccupied
- StationReleased
- StationFaultDetected
- StationRecovered
- MaintenanceScheduled

### Telemetry Events

- TelemetryReceived
- PowerUpdated
- EnergyDelivered
- BatteryStateUpdated

### Simulation Events

- SimulationStarted
- SimulationFinished
- ScenarioExecuted

### AI Events

- PredictionGenerated
- ModelTrained
- DatasetExported

Additional events may be introduced as new domains evolve.

---

# 14. Event Lifecycle

Business events follow a common lifecycle.

```text
Business Action

        │

        ▼

Business Validation

        │

        ▼

Domain Event

        │

        ▼

Persistence

        │

        ▼

Internal Publication

        │

        ▼

Interested Consumers
```

Events must represent facts that have already occurred.

Consumers should never rely on events to enforce business validation.

---

# 15. Technology Stack

Technology selection prioritizes simplicity, ecosystem maturity and compatibility with data engineering and artificial intelligence workflows.

## Backend

- Python 3.13
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic

---

## Database

- PostgreSQL

---

## Frontend

- React
- TypeScript
- Vite

---

## Development Environment

- Docker
- Docker Compose
- Make
- pre-commit

---

## Documentation

- OpenAPI
- MkDocs
- Mermaid

---

## Testing

- pytest
- pytest-asyncio
- Testcontainers
- Coverage.py

---

## Code Quality

- Ruff
- Black
- MyPy
- Bandit
- pip-audit

---

## Observability

- OpenTelemetry
- Prometheus
- Grafana
- Loki
- Tempo

---

# 16. Infrastructure Philosophy

The entire platform must be executable using a single local environment.

Every developer should be capable of reproducing the complete experimental environment without manual infrastructure configuration.

The reference environment includes:

- Backend API;
- Frontend;
- PostgreSQL;
- Prometheus;
- Grafana;
- Loki;
- Tempo.

No cloud provider shall be required during development.

Cloud deployment should remain an implementation detail rather than an architectural dependency.

# 17. DevSecOps

Modern Software Engineering requires software quality to be continuously verified throughout the development lifecycle.

For this reason, SCEP adopts a **DevSecOps** approach in which code quality, security and deployment automation are integrated into the development process from the first iteration.

Every change submitted to the project shall be validated through an automated Continuous Integration (CI) pipeline.

The pipeline is responsible for preventing defective, insecure or non-compliant code from being integrated into the main branch.

The minimum validation pipeline shall execute the following stages:

```text
Source Code

      │

      ▼

Formatting

      │

      ▼

Linting

      │

      ▼

Static Type Checking

      │

      ▼

Unit Tests

      │

      ▼

Integration Tests

      │

      ▼

Coverage Validation

      │

      ▼

Security Scanning

      │

      ▼

Dependency Audit

      │

      ▼

Docker Build

      │

      ▼

Artifact Publication
```

Future versions of the platform may extend this pipeline with automatic deployments, infrastructure provisioning and cloud-native delivery strategies.

---

# 18. Observability Strategy

Observability is a fundamental capability of SCEP.

Unlike traditional monitoring solutions that focus exclusively on infrastructure availability, observability in SCEP is intended to provide visibility into both software behavior and business behavior.

The platform shall expose three complementary sources of operational information.

## Structured Logs

Every application log shall be machine-readable.

Logs should include contextual information whenever available.

Examples include:

- timestamp;
- request identifier;
- correlation identifier;
- authenticated user;
- charging station identifier;
- reservation identifier;
- charging session identifier;
- event type;
- execution duration.

Structured logs enable efficient querying and correlation across different platform modules.

---

## Metrics

Operational metrics shall be continuously collected and exported.

Examples include:

### Platform Metrics

- HTTP request latency;
- request throughput;
- active users;
- application errors;
- CPU usage;
- memory usage.

### Business Metrics

- reservation rate;
- reservation cancellation rate;
- charger occupancy;
- charging session duration;
- delivered energy;
- charger utilization;
- average waiting time.

### Research Metrics

- simulation execution time;
- generated events;
- generated datasets;
- prediction accuracy;
- experiment duration.

---

## Distributed Tracing

Distributed traces provide visibility into the execution flow of complex business operations.

Tracing shall support:

- API requests;
- business operations;
- database interactions;
- event publication;
- asynchronous processing.

Tracing data will also support architectural evaluation during the research activities.

---

## Health Monitoring

Each service shall expose health endpoints describing its operational state.

Health information should distinguish between:

- application availability;
- database connectivity;
- external dependency status;
- internal subsystem status.

---

# 19. Quality Strategy

Software quality shall be evaluated continuously throughout the project.

Quality is considered an architectural concern rather than a final verification activity.

The platform adopts multiple complementary quality practices.

## Coding Standards

The project shall follow a consistent coding style.

Formatting and linting must be automatically enforced.

Manual formatting should never be required.

---

## Static Analysis

Static analysis shall identify:

- code smells;
- type inconsistencies;
- security vulnerabilities;
- dependency issues;
- architectural violations.

---

## Architectural Consistency

Module boundaries shall remain explicit.

Dependencies between modules should always respect the architectural rules established by this document.

No module shall directly access another module's internal implementation.

---

## Documentation

Architecture documentation shall evolve together with the implementation.

Major architectural decisions must be documented before implementation.

---

# 20. Testing Strategy

Testing is considered one of the primary mechanisms for preserving architectural quality.

The platform follows a testing pyramid emphasizing fast feedback while maintaining confidence in production behavior.

The following testing levels shall be implemented.

## Unit Tests

Validate isolated business rules.

These tests should execute quickly and avoid external dependencies.

---

## Integration Tests

Validate interactions between application components.

Integration tests shall execute against real infrastructure whenever practical.

Examples include:

- PostgreSQL;
- API endpoints;
- persistence layer.

---

## End-to-End Tests

Validate complete user workflows.

These tests reproduce realistic application scenarios.

---

## Architecture Tests

Architecture tests verify compliance with the intended modular structure.

Examples include:

- forbidden dependencies;
- module isolation;
- package organization.

---

## Simulation Validation

The Simulation Engine shall be validated independently.

Simulation scenarios must produce deterministic results whenever identical parameters and random seeds are supplied.

This requirement is essential for experiment reproducibility.

---

# 21. Research Dataset

One of the primary outputs of SCEP is not the application itself, but the operational datasets continuously generated during platform execution.

Every reservation, charging session, telemetry update and simulated event contributes to the creation of research datasets.

Generated datasets should satisfy the following characteristics:

- reproducible;
- configurable;
- versioned;
- documented;
- suitable for analytical processing.

Potential dataset contents include:

- reservation history;
- charging sessions;
- occupancy evolution;
- charger utilization;
- energy consumption;
- telemetry events;
- simulation metadata;
- prediction results.

These datasets support experimentation in analytics, optimization and machine learning.

---

# 22. Experimentation Framework

Experimentation is a first-class capability of the platform.

Each experiment shall be reproducible and explicitly described.

An experiment consists of:

- scenario definition;
- simulation configuration;
- execution parameters;
- generated events;
- collected metrics;
- resulting datasets;
- experiment report.

Typical experiments include:

- evaluating reservation strategies;
- analyzing occupancy peaks;
- comparing scheduling algorithms;
- validating prediction models;
- measuring architectural performance;
- evaluating operational metrics.

Future research may introduce additional experiment types without requiring architectural changes.

---

# 23. Operational Metrics

The platform shall calculate operational indicators automatically.

Initial metrics include:

### Utilization

- charger utilization rate;
- average occupancy;
- idle time;
- charging time.

### Reservations

- reservation success rate;
- cancellation rate;
- no-show rate;
- average reservation lead time.

### Infrastructure

- charger availability;
- charger failures;
- maintenance frequency;
- recovery time.

### Energy

- delivered energy;
- average charging power;
- charging efficiency.

### Artificial Intelligence

- prediction accuracy;
- prediction error;
- model execution time;
- inference latency.

These indicators support both operational management and research activities.

---

# 24. Roadmap

Platform development shall occur incrementally.

## Phase 1 — Platform Foundation

Deliverables:

- project structure;
- development environment;
- CI pipeline;
- authentication;
- documentation.

---

## Phase 2 — Smart Charging Domain

Deliverables:

- charging stations;
- reservations;
- charging sessions.

Current progress: charging stations and Reservations are implemented; Charging Sessions are
documented in draft SPEC-007 and are not yet implemented.

---

## Phase 3 — Event Platform

Deliverables:

- domain events;
- event publication;
- event persistence.

---

## Phase 4 — Simulation Engine

Deliverables:

- configurable scenarios;
- synthetic users;
- synthetic vehicles;
- synthetic telemetry.

---

## Phase 5 — Analytics

Deliverables:

- dashboards;
- KPIs;
- historical reports.

---

## Phase 6 — Observability

Deliverables:

- metrics;
- logs;
- traces;
- dashboards.

---

## Phase 7 — AI Experimentation

Deliverables:

- dataset generation;
- occupancy prediction;
- experiment reports.

---

## Phase 8 — Research Validation

Deliverables:

- experimental evaluation;
- architectural assessment;
- final documentation;
- dissertation support artifacts.

---

# 25. Success Criteria

The project will be considered successful when the following conditions are simultaneously satisfied.

## Platform

- the platform supports complete Smart Charging workflows;
- all major architectural modules are operational;
- the environment is reproducible using containers.

---

## Software Engineering

- modular architecture is preserved;
- automated testing is established;
- DevSecOps pipeline is operational;
- observability infrastructure is available.

---

## Research

- realistic synthetic datasets are generated;
- experiments are reproducible;
- operational metrics are available;
- AI models can consume generated datasets.

---

## Academic

The project demonstrates the practical integration of:

- Modern Software Engineering;
- Internet of Things;
- Data Engineering;
- Artificial Intelligence;
- Software Architecture;
- DevSecOps;
- Observability;
- Applied Research.

---

# 26. Final Considerations

The Smart Charging Experimentation Platform is intentionally designed as a research platform rather than a conventional business application.

Its architecture prioritizes extensibility, reproducibility and experimentation, allowing new research topics to be incorporated with minimal architectural impact.

Although Smart Charging is the initial domain, the architectural principles established in this document are domain-independent and may support future experimentation in other cyber-physical systems.

This document establishes the architectural vision that guides every subsequent specification, architectural decision record (ADR) and implementation activity within the project.

All future specifications shall conform to the principles, quality attributes and architectural boundaries defined herein.
