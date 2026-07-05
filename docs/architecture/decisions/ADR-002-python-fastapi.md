# ADR-002 — Adopt Python and FastAPI for the Backend API

**Status:** Accepted
**Date:** 2026
**Related Specs:**

* `001-architecture-vision.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`
* `006-quality-attributes.md`
* `008-deployment-runtime-view.md`

---

# Context

The Smart Charging Experimentation Platform (SCEP) requires a backend capable of supporting both operational workflows and research-oriented capabilities.

The Backend API must provide:

* REST APIs;
* authentication and authorization;
* Smart Charging business workflows;
* telemetry ingestion;
* domain event persistence;
* analytics endpoints;
* dataset export;
* prediction result ingestion;
* observability instrumentation.

The platform also has a strong relationship with data engineering, simulation and artificial intelligence.

For this reason, the backend technology stack should align with both web application development and research workflows.

---

# Decision

The Backend API will be implemented using **Python 3.13** and **FastAPI**.

The initial backend stack will include:

* Python 3.13;
* FastAPI;
* Pydantic;
* SQLAlchemy;
* Alembic;
* pytest;
* Ruff;
* Black;
* MyPy;
* Bandit;
* pip-audit.

---

# Rationale

Python was selected because it provides a mature and widely adopted ecosystem for:

* web APIs;
* data processing;
* simulation;
* analytics;
* machine learning;
* automation;
* experimentation.

FastAPI was selected because it offers:

* high developer productivity;
* native OpenAPI generation;
* strong integration with Pydantic;
* async support;
* good performance for API workloads;
* clear request and response modeling.

This decision supports SCEP's research-oriented nature by reducing friction between backend development, dataset generation and AI experimentation.

---

# Alternatives Considered

## Java with Spring Boot

Spring Boot is a mature enterprise backend framework with strong support for modular applications, security, observability and persistence.

It was considered because it is widely used in production-grade systems and aligns well with enterprise software engineering.

Rejected because Python offers better alignment with the project’s simulation, data analysis and AI experimentation goals.

---

## Node.js with NestJS

NestJS provides a structured backend framework with strong TypeScript support and good modularity.

It was considered because it integrates naturally with a TypeScript frontend.

Rejected because the project benefits more from Python’s data science and machine learning ecosystem.

---

## Python with Django

Django provides a mature full-stack web framework.

It was considered due to its batteries-included approach.

Rejected because SCEP requires an API-first architecture, modular backend organization and lightweight service boundaries. FastAPI better supports these goals.

---

## Python with Flask

Flask is simple and flexible.

It was considered because of its low complexity.

Rejected because FastAPI provides stronger typing, automatic OpenAPI support and better request/response validation through Pydantic.

---

# Consequences

## Positive Consequences

* strong alignment with AI and data workflows;
* easier integration with notebooks and research scripts;
* automatic API documentation;
* productive development experience;
* strong schema validation;
* good testing ecosystem;
* reduced impedance between backend and AI experimentation.

---

## Negative Consequences

* Python may offer lower raw performance than compiled languages;
* architecture discipline must be actively maintained;
* async and database session management require care;
* type safety depends on tooling and project discipline;
* enterprise-grade patterns must be explicitly designed rather than assumed by the framework.

---

# Architectural Rules

The backend implementation must follow these rules:

* FastAPI routers must not contain business rules;
* Pydantic models are used for external API contracts;
* domain logic must remain independent from FastAPI;
* SQLAlchemy models must not leak into API responses;
* database migrations must be managed through Alembic;
* all public APIs must be documented through OpenAPI;
* type checking must be enforced through MyPy;
* formatting and linting must be automated;
* security scanning must be included in CI.

---

# Quality Attributes Supported

This decision supports the following quality attributes:

| Quality Attribute | Support                                                       |
| ----------------- | ------------------------------------------------------------- |
| Maintainability   | clear Python modules, typed contracts and explicit boundaries |
| Testability       | mature pytest ecosystem                                       |
| Reproducibility   | simple dependency and environment management                  |
| Observability     | OpenTelemetry-compatible ecosystem                            |
| Extensibility     | easy integration with analytics and AI libraries              |
| Data Quality      | schema validation through Pydantic                            |
| Productivity      | fast development cycle and automatic OpenAPI documentation    |

---

# Risks and Mitigations

## Risk: Architectural erosion

Because Python is flexible, modules may become coupled if boundaries are not enforced.

Mitigation:

* architecture tests;
* strict module conventions;
* code reviews;
* ADRs and specifications.

---

## Risk: Runtime performance limitations

Python may be less efficient for CPU-intensive workloads.

Mitigation:

* keep heavy AI training outside the transactional Backend API;
* use external AI Research Environment;
* optimize only after measurement;
* consider background workers if needed.

---

## Risk: Type safety limitations

Python type hints are optional.

Mitigation:

* enforce MyPy in CI;
* use Pydantic for schema validation;
* avoid untyped public interfaces.

---

## Risk: Dependency vulnerabilities

Python ecosystems can introduce vulnerable dependencies.

Mitigation:

* use pip-audit;
* use dependency pinning;
* scan dependencies in CI.

---

# Future Evolution

The Python and FastAPI stack is expected to remain the foundation of the Backend API during the project.

If future requirements demand separation of workloads, specific capabilities may evolve into independent services or workers, especially:

* telemetry ingestion;
* analytics processing;
* dataset export;
* prediction ingestion.

This evolution should preserve the API-first and event-driven principles established in the architecture documents.

---

# Decision Outcome

The Backend API will be implemented using **Python 3.13 and FastAPI**, supported by SQLAlchemy, Pydantic, Alembic and a Python-based quality toolchain.

This stack is considered the best fit for SCEP because it supports backend development, research workflows, simulation, analytics and AI experimentation within a coherent technology ecosystem.
