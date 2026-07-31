# ADR-008 — Separate AI Experimentation from the Transactional Platform

**Status:** Accepted
**Date:** 2026
**Related Specs:**

* `001-architecture-vision.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`
* `005-data-view.md`
* `006-quality-attributes.md`
* `008-deployment-runtime-view.md`
* `ADR-009-dataset-export-snapshot-source-and-provenance-strategy.md`
* `../../specs/SPEC-012-predictions.md`

---

# Context

One of the primary objectives of the Smart Charging Experimentation Platform (SCEP) is to support Artificial Intelligence research using operational and simulated Smart Charging data.

The platform is expected to:

* generate datasets;
* support feature engineering;
* train predictive models;
* evaluate model performance;
* expose prediction results.

A key architectural decision concerns where AI-related activities should execute.

Possible approaches include:

* embedding model training inside the Backend API;
* executing AI workloads as background jobs;
* separating AI experimentation into an independent environment.

Since SCEP is intended as both a software platform and a research environment, the architecture must balance operational stability with experimental flexibility.

---

# Decision

AI experimentation shall be performed in an **independent AI Research Environment**, external to the transactional Backend API.

The Backend API is responsible for:

* producing operational data;
* exporting datasets;
* storing prediction results;
* exposing prediction APIs.

The AI Research Environment is responsible for:

* feature engineering;
* model training;
* model evaluation;
* experiment execution;
* prediction generation.

Communication between both environments shall occur through:

* dataset exports;
* public REST APIs.

The Backend API shall not perform model training.
The Backend API shall not execute model inference.

---

# Rationale

Machine Learning workloads differ significantly from transactional business workloads.

Training models requires:

* iterative experimentation;
* computationally intensive processing;
* frequent dependency changes;
* exploratory analysis.

These activities are incompatible with the responsibilities of a transactional Backend API.

Separating AI experimentation preserves:

* architectural simplicity;
* operational stability;
* research flexibility.

It also reflects common industry practices, where production systems and data science environments evolve independently while exchanging well-defined artifacts.

---

# Alternatives Considered

## AI Inside the Backend API

Model training and inference execute inside the transactional application.

Advantages:

* single deployable application;
* simple communication.

Rejected because:

* training workloads interfere with transactional operations;
* additional dependencies increase application complexity;
* experimentation becomes more difficult.

---

## Dedicated AI Research Environment

Model development occurs outside the operational platform.

Advantages:

* independent lifecycle;
* isolated dependencies;
* unrestricted experimentation;
* better reproducibility.

Selected.

---

## External Managed AI Platform

Use cloud-based machine learning services.

Examples:

* managed notebooks;
* managed training services.

Rejected because:

* introduces unnecessary cloud dependency;
* reduces reproducibility;
* exceeds the scope of the project.

---

# Consequences

## Positive Consequences

* clear separation of concerns;
* simplified Backend API;
* unrestricted AI experimentation;
* easier dependency management;
* independent evolution of AI workflows;
* realistic software architecture.

---

## Negative Consequences

* additional executable environment;
* dataset exchange between systems;
* prediction publication requires explicit APIs;
* increased operational complexity compared to an embedded solution.

---

# Architectural Rules

The following rules are mandatory.

* The Backend API shall never train machine learning models.
* The Backend API shall never execute machine learning model inference.
* AI workflows shall consume exported datasets.
* AI workflows shall not access PostgreSQL directly.
* Prediction results shall be published through public APIs.
* AI experiments shall be reproducible.
* AI dependencies shall remain isolated from Backend API dependencies.

---

# Responsibilities

## Backend API

Responsible for:

* transactional processing;
* telemetry persistence;
* event persistence;
* dataset generation;
* prediction storage;
* prediction APIs.

For SPEC-012 Version 1, prediction storage means immutable metadata plus one complete 168-bucket
recurring weekly profile for one Facility, Station or Connector scope. The Backend API validates
and exposes externally generated values; limited model and run references do not make it a Model
Registry.

The Backend API owns operational data.

---

## AI Research Environment

Responsible for:

* feature engineering;
* model selection;
* hyperparameter tuning;
* model training;
* validation;
* model comparison;
* prediction generation;
* experiment documentation.

The AI Research Environment owns research activities.

It also owns inference execution. Publication transfers completed prediction results, not an
executable model, feature pipeline or inference request.

---

# Data Flow

The interaction between both environments follows the architecture below.

```text
Operational Data

        │

        ▼

Backend API

        │

Dataset Export

        │

        ▼

AI Research Environment

        │

Feature Engineering

        │

        ▼

Model Training

        │

        ▼

Model Evaluation

        │

        ▼

Prediction Results

        │

REST API

        │

        ▼

Backend API

        │

Dashboards
```

The Backend API remains the authoritative source of operational information.

The AI Research Environment consumes data but does not modify transactional state.

---

# Dataset Strategy

Datasets are considered first-class research artifacts.

Every exported dataset shall contain universal provenance sufficient to identify:

* dataset identifier;
* export timestamp;
* platform version;
* source boundary;
* schema version;
* canonical export configuration;
* generation and integrity metadata.

Experiment identifiers, feature descriptions, simulation seeds and simulation parameters are
conditional lineage. They shall be included only when an implemented source specification can
associate them truthfully with the exported records. Feature descriptions normally belong to the
AI Research Environment because feature engineering executes outside the Backend API.

Concrete supported formats are selected by the corresponding functional specification. Portable
formats may include:

* CSV;
* JSON;
* Parquet.

SPEC-011 Version 1 selects CSV and Parquet. Future formats may be added without changing the
architectural principles.

ADR-009 defines the Version 1 snapshot, source and provenance strategy.

---

# Model Lifecycle

The platform separates the lifecycle of operational software from the lifecycle of machine learning models.

Model lifecycle includes:

* dataset selection;
* feature engineering;
* training;
* validation;
* evaluation;
* publication of prediction results.

This lifecycle remains independent from transactional software releases.

---

# Relationship with Smart Charging

The first AI capability planned for SCEP is:

**Charging Station Occupancy Prediction**

Future research topics may include:

* charging demand forecasting;
* predictive maintenance;
* anomaly detection;
* reservation optimization;
* charging recommendation;
* energy optimization.

These capabilities shall be implemented inside the AI Research Environment.

---

# Quality Attributes Supported

This decision primarily supports:

| Quality Attribute | Support                                                     |
| ----------------- | ----------------------------------------------------------- |
| Maintainability   | Clear separation between business software and AI workflows |
| Extensibility     | Independent evolution of AI experiments                     |
| Reproducibility   | Isolated experiment execution                               |
| Testability       | AI and backend validated independently                      |
| Modularity        | Distinct operational and research responsibilities          |
| Research Support  | Flexible experimentation environment                        |

---

# Risks and Mitigations

## Risk: Dataset Incompatibility

Changes in exported schemas may break AI workflows.

Mitigation:

* version dataset schemas;
* document exported fields;
* maintain backward compatibility whenever practical.

---

## Risk: Divergence Between Operational Data and AI Expectations

Feature definitions may become inconsistent over time.

Mitigation:

* centralized dataset generation;
* documented feature definitions;
* experiment metadata.

---

## Risk: Model Drift

Prediction quality may degrade as operational behavior evolves.

Mitigation:

* periodic model retraining;
* experiment versioning;
* evaluation dashboards.

---

# Future Evolution

Future improvements may include:

* automated feature engineering;
* Feature Store integration;
* ML experiment tracking;
* model registry;
* automated retraining pipelines;
* online inference services;
* reinforcement learning experiments.

These enhancements should remain external to the transactional Backend API.

---

# Relationship with Other Architectural Decisions

This decision complements:

* **ADR-001**, by keeping AI outside the Modular Monolith.
* **ADR-003**, by allowing prediction-related events to integrate naturally with the event-driven architecture.
* **ADR-004**, by treating PostgreSQL as the authoritative operational data source while avoiding direct database access from AI workflows.
* **ADR-005**, by establishing a parallel architecture in which both the Digital Twin Simulation Engine and the AI Research Environment are external producers and consumers of the platform.

Together, these decisions reinforce the separation between operational software and research infrastructure.

---

# Decision Outcome

The AI Research Environment will remain an independent component throughout the lifecycle of SCEP.

The Backend API is responsible for generating trustworthy operational data and exposing controlled integration points, while the AI Research Environment remains free to evolve independently, supporting experimentation, model development and scientific research without compromising the stability or simplicity of the transactional platform.

This decision strengthens SCEP's identity as a research-oriented Smart Charging experimentation platform and establishes a scalable foundation for future Artificial Intelligence studies.
