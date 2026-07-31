# ADR-005 — Adopt an External Digital Twin Simulation Engine

**Status:** Accepted
**Date:** 2026
**Amended by:** SPEC-013 Version 1
**Related Specs:**

* `001-architecture-vision.md`
* `002-context-diagram.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`
* `005-data-view.md`
* `006-quality-attributes.md`
* `008-deployment-runtime-view.md`
* `../../specs/SPEC-013-simulation-engine.md`

---

# Context

One of the primary goals of the Smart Charging Experimentation Platform (SCEP) is to provide a reproducible environment for Smart Charging research.

Unlike conventional charging management systems, SCEP must support:

* synthetic data generation;
* reproducible experiments;
* controlled simulation scenarios;
* evaluation of AI models;
* architectural experimentation.

The platform therefore requires a mechanism capable of generating realistic operational behavior without depending on physical charging infrastructure.

A key architectural question was whether the simulation capability should be implemented as an internal backend module or as an independent application.

---

# Decision

The **Digital Twin Simulation Engine** shall be implemented as an **independent application**, external to the Backend API.

The Simulation Engine interacts with SCEP exclusively through public APIs.

The Simulation Engine is **not part of the Modular Monolith**.

Simulated domain operations continue to use the same public contracts and business rules as normal clients. However, accelerated and reproducible execution requires the Backend API to recognize a narrowly scoped simulation context for authorization, logical time, provenance and idempotency. This context does not move behavioral simulation into the backend and does not permit domain-rule bypass.

---

# Rationale

Keeping the Simulation Engine outside the Backend API preserves a clean separation between:

* operational software;
* experimentation infrastructure.

The Backend API remains responsible for:

* business rules;
* authentication and authorization;
* persistence;
* domain events;
* simulation-run context validation;
* analytics;
* dataset generation.

The Simulation Engine becomes responsible for generating realistic external behavior, controlling its logical event plan and advancing scenario time through authorized requests.

This separation ensures that business logic is never coupled to simulation behavior.

The platform therefore remains capable of supporting:

* simulated environments;
* test clients;
* future physical chargers;
* future third-party integrations;

without embedding scenario models in the transactional application.

---

# Alternatives Considered

## Internal Simulation Module

The simulator executes inside the Backend API.

Advantages:

* simpler implementation;
* direct access to business objects.

Rejected because:

* simulation becomes coupled to business logic;
* unrealistic execution model;
* reduced architectural flexibility;
* difficult replacement by real infrastructure.

---

## External Simulation Engine

The simulator behaves as an independent client.

Advantages:

* realistic communication model;
* reusable APIs;
* better architectural isolation;
* easier experimentation;
* future compatibility with physical devices.

Selected.

---

## Hardware-in-the-Loop Simulation

Simulation performed using physical charging stations.

Advantages:

* maximum realism.

Rejected because:

* expensive infrastructure;
* low reproducibility;
* impractical for continuous experimentation;
* outside project scope.

---

# Consequences

## Positive Consequences

* realistic client behavior;
* reusable public APIs;
* improved architectural isolation;
* independent simulator evolution;
* reproducible experiments;
* easier automated testing;
* future compatibility with real charging infrastructure;
* traceable and idempotent accelerated simulation runs.

---

## Negative Consequences

* additional executable application;
* API communication instead of direct method calls;
* simulator lifecycle managed independently;
* increased deployment complexity compared to an internal module;
* backend support for run authorization, logical time and provenance;
* coordinated transactional handling for simulation idempotency.

---

# Architectural Rules

The following rules are mandatory.

* The Simulation Engine shall never access PostgreSQL directly.
* The Simulation Engine shall never invoke Backend API internal modules.
* Every interaction shall occur through public REST APIs.
* Simulated requests shall be authenticated as the acting user and authorized for a controlled execution.
* Simulation scenarios shall be reproducible.
* Simulation configuration shall be externalized.
* Simulation execution shall be independent from backend deployment.
* The Backend API shall not execute scenario behavior or probabilistic user models.
* Logical time shall be supplied by the simulator and validated by the Backend API.
* Simulation context shall not bypass normal domain invariants.
* Provenance and idempotency metadata shall be assigned by the Backend API, never trusted from normal payload fields.

---

# Responsibilities

## Backend API

Responsible for:

* validating requests;
* authenticating the EVDriver and simulation execution context;
* enforcing SimulationRun lifecycle, scope and logical-time boundaries;
* executing business rules through existing domain services;
* persisting transactional data and simulation provenance;
* publishing Domain Events;
* exporting datasets;
* recording successful simulation-event receipts.

The Backend API recognizes whether a mutable request belongs to an authorized SimulationRun only to enforce time, scope, provenance and idempotency. It does not know or execute the external behavioral scenario.

---

## Simulation Engine

Responsible for:

* consuming pre-created synthetic users, vehicles and infrastructure;
* generating charging-station usage behavior;
* creating reservations;
* starting charging sessions;
* finishing charging sessions;
* generating telemetry;
* generating cancellations and no-show behavior through normal platform flows;
* executing configurable scenarios;
* maintaining the deterministic event plan, logical clock, checkpoints and execution report.

Version 1 does not require the Simulation Engine to create Users, Vehicles, Facilities, Stations or Connectors. Those resources are provisioned administratively before execution.

The Simulation Engine does not implement business rules.

Its responsibility is to produce realistic external behavior and react to the Backend API's authoritative outcomes.

---

# Communication Model

The interaction follows the same public API boundary expected from any external client, with an additional validated simulation context for accelerated execution.

```text
Simulation Engine

        │

HTTPS / REST APIs
EVDriver authentication
SimulationRun context

        │

        ▼

Backend API

        │

Simulation authorization
Logical-time validation
Business validation

        │

        ▼

PostgreSQL

        │

        ▼

Domain Events

        │

        ▼

Analytics
Datasets
Observability
```

This communication model intentionally mirrors future production integrations while preserving controlled research execution.

---

# Simulation Philosophy

The Simulation Engine represents a **Digital Twin Environment**.

Its purpose is not simply generating random requests.

Instead, it reproduces realistic Smart Charging behavior.

Simulation scenarios may include:

* residential condominiums;
* university campuses;
* corporate parking facilities;
* shopping centers;
* public charging stations.

Each scenario may define externally:

* configured users and vehicles;
* arrival distributions;
* charging duration;
* reservation behavior;
* cancellation probability;
* no-show probability;
* infrastructure preferences;
* telemetry sampling behavior;
* retry, rescheduling and abandonment policy.

Detailed infrastructure failures, maintenance windows, battery models and other advanced behaviors remain future scenario capabilities unless approved by a later specification.

---

# Reproducibility

Every simulation shall support deterministic planning.

The following metadata shall be recorded or externally preserved:

* experiment or scenario identifier;
* SimulationRun identifier;
* random seed;
* execution timestamp;
* simulator version;
* platform version when available;
* scenario version and digest.

Executing the same scenario using the same configuration, bootstrap, seed and simulator version shall generate the same initial event plan. Final operational results may differ when external platform state differs.

This capability directly supports the research objectives of SCEP.

---

# Relationship with Artificial Intelligence

The Simulation Engine does not execute AI models.

Its responsibility is to generate high-quality operational data.

AI experiments consume datasets generated by SCEP and may publish completed prediction results through separately authorized contracts.

This separation preserves a clear distinction between:

* data generation;
* model training;
* prediction publication and serving.

---

# Quality Attributes Supported

This decision primarily supports:

| Quality Attribute | Support |
| ----------------- | ------- |
| Reproducibility | Deterministic event planning and traceable runs |
| Maintainability | Clear separation of scenario behavior and domain logic |
| Extensibility | New external scenario models without backend embedding |
| Testability | End-to-end validation through public APIs |
| Modularity | Independent simulator lifecycle |
| Security | Explicit run scope and authenticated logical-time use |
| Research Support | High-quality synthetic datasets |

---

# Risks and Mitigations

## Risk: Unrealistic Simulation

Synthetic behavior may diverge from real operational environments.

Mitigation:

* configurable probabilistic models;
* realistic operational parameters;
* multiple scenario definitions;
* continuous refinement using literature and domain knowledge.

---

## Risk: API Evolution

Changes to public APIs may break the simulator.

Mitigation:

* versioned APIs;
* contract testing;
* OpenAPI documentation;
* backward compatibility whenever practical.

---

## Risk: Excessive Scenario Complexity

Highly configurable simulations may become difficult to maintain.

Mitigation:

* reusable scenario templates;
* configuration validation;
* documented simulation presets;
* strict Version 1 behavioral scope in SPEC-013.

---

## Risk: Logical Time Escapes the Simulation Scope

Accelerated time could affect normal data or another run.

Mitigation:

* authenticated run-scoped execution context;
* explicit Facility and EVDriver associations;
* provenance on operational roots;
* partitioned temporal reconciliation;
* coordinated transactions and run-row locking;
* dedicated simulation Facilities for Version 1.

---

# Future Evolution

Future versions of the Simulation Engine may support:

* OCPP protocol simulation;
* multiple charger manufacturers;
* electrical grid constraints;
* dynamic electricity pricing;
* weather influence;
* richer user behavioral models;
* reinforcement learning agents;
* distributed simulation workers;
* permanent non-human simulator identity;
* explicit synthetic-data isolation and retention.

These enhancements shall remain independent from the Backend API's behavioral logic.

---

# Decision Outcome

The Digital Twin Simulation Engine will remain an independent application throughout the project lifecycle.

By interacting with SCEP exclusively through public APIs, the simulator preserves architectural boundaries, validates the platform under realistic operating conditions and produces reproducible datasets for Smart Charging research.

SPEC-013 clarifies that safe accelerated execution requires the Backend API to recognize a restricted SimulationRun context. This amendment does not reverse the external-engine decision: the backend validates execution context and domain invariants, while all scenario behavior remains external.

This decision reinforces SCEP's identity as a **research and experimentation platform**, where simulation is an external producer of operational behavior rather than an internal behavioral implementation concern.
