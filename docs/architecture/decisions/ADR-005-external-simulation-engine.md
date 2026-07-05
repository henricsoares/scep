# ADR-005 — Adopt an External Digital Twin Simulation Engine

**Status:** Accepted
**Date:** 2026
**Related Specs:**

* `001-architecture-vision.md`
* `002-context-diagram.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`
* `005-data-view.md`
* `006-quality-attributes.md`
* `008-deployment-runtime-view.md`

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

From the perspective of the Backend API, simulated entities are indistinguishable from future real-world clients.

The Simulation Engine is **not part of the Modular Monolith**.

---

# Rationale

Keeping the Simulation Engine outside the Backend API preserves a clean separation between:

* operational software;
* experimentation infrastructure.

The Backend API remains responsible for:

* business rules;
* persistence;
* domain events;
* analytics;
* dataset generation.

The Simulation Engine becomes responsible for generating realistic external behavior.

This separation ensures that business logic is never coupled to simulation logic.

The platform therefore remains capable of supporting:

* simulated environments;
* test clients;
* future physical chargers;
* future third-party integrations;

without requiring changes to its internal architecture.

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
* future compatibility with real charging infrastructure.

---

## Negative Consequences

* additional executable application;
* API communication instead of direct method calls;
* simulator lifecycle managed independently;
* increased deployment complexity compared to an internal module.

---

# Architectural Rules

The following rules are mandatory.

* The Simulation Engine shall never access PostgreSQL directly.
* The Simulation Engine shall never invoke Backend API internal modules.
* Every interaction shall occur through public REST APIs.
* Simulated requests shall be authenticated.
* Simulation scenarios shall be reproducible.
* Simulation configuration shall be externalized.
* Simulation execution shall be independent from backend deployment.

---

# Responsibilities

## Backend API

Responsible for:

* validating requests;
* executing business rules;
* persisting transactional data;
* publishing Domain Events;
* exporting datasets.

The Backend API does not know whether requests originate from simulated or real clients.

---

## Simulation Engine

Responsible for:

* generating synthetic users;
* generating vehicles;
* generating charging stations usage;
* creating reservations;
* starting charging sessions;
* finishing charging sessions;
* generating telemetry;
* generating failures;
* generating maintenance events;
* executing configurable scenarios.

The Simulation Engine does not implement business rules.

Its responsibility is to produce realistic external behavior.

---

# Communication Model

The interaction follows the same communication model expected from any external client.

```text id="9s71cm"
Simulation Engine

        │

HTTPS / REST APIs

        │

        ▼

Backend API

        │

Business Validation

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

This communication model intentionally mirrors future production integrations.

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

Each scenario defines:

* number of users;
* number of vehicles;
* charger availability;
* arrival distributions;
* charging duration;
* battery state of charge;
* reservation behavior;
* cancellation probability;
* no-show probability;
* equipment failures;
* maintenance windows.

---

# Reproducibility

Every simulation shall support deterministic execution.

The following metadata shall be recorded:

* experiment identifier;
* simulation identifier;
* random seed;
* execution timestamp;
* simulator version;
* platform version;
* scenario configuration.

Executing the same scenario using the same configuration should produce statistically equivalent results.

This capability directly supports the research objectives of SCEP.

---

# Relationship with Artificial Intelligence

The Simulation Engine does not execute AI models.

Its responsibility is to generate high-quality operational data.

AI experiments consume datasets generated by SCEP.

This separation preserves a clear distinction between:

* data generation;
* model training;
* prediction serving.

---

# Quality Attributes Supported

This decision primarily supports:

| Quality Attribute | Support                                          |
| ----------------- | ------------------------------------------------ |
| Reproducibility   | Deterministic experiment execution               |
| Maintainability   | Clear separation of concerns                     |
| Extensibility     | New simulation scenarios without backend changes |
| Testability       | End-to-end API validation                        |
| Modularity        | Independent simulator lifecycle                  |
| Research Support  | High-quality synthetic datasets                  |

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
* documented simulation presets.

---

# Future Evolution

Future versions of the Simulation Engine may support:

* OCPP protocol simulation;
* multiple charger manufacturers;
* electrical grid constraints;
* dynamic electricity pricing;
* weather influence;
* user behavioral models;
* reinforcement learning agents;
* distributed simulation workers.

These enhancements should remain independent from the Backend API.

---

# Decision Outcome

The Digital Twin Simulation Engine will remain an independent application throughout the project lifecycle.

By interacting with SCEP exclusively through public APIs, the simulator preserves architectural boundaries, validates the platform under realistic operating conditions and produces reproducible datasets for Smart Charging research.

This decision reinforces SCEP's identity as a **research and experimentation platform**, where simulation is an external producer of operational behavior rather than an internal implementation concern.
