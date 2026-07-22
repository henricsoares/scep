# Architecture View 008 — Deployment Runtime View

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

This document describes the runtime deployment architecture of the **Smart Charging Experimentation Platform (SCEP)**.

Unlike previous architectural documents, which focus on logical organization, this specification defines how the platform executes as a complete software system.

It describes:

* runtime topology;
* execution environments;
* container organization;
* network communication;
* infrastructure services;
* configuration strategy;
* deployment process;
* future evolution towards production environments.

The primary objective is to guarantee that every researcher and developer can reproduce the complete experimentation environment with minimal effort.

---

# 2. Deployment Philosophy

SCEP follows a **Reproducible Development Environment** philosophy.

Every contributor should be capable of executing the complete platform locally without requiring external cloud infrastructure.

The entire runtime environment shall be provisioned using containers.

This approach provides:

* reproducibility;
* portability;
* environment consistency;
* simplified onboarding;
* infrastructure versioning.

Cloud deployment is considered an implementation detail rather than an architectural dependency.

---

# 3. Runtime Architecture

The reference runtime environment is illustrated below.

```text
                   Developer Workstation

                            │

                    Docker Compose

                            │

     ┌──────────────────────┼────────────────────────┐

     │                      │                        │

 Frontend              Backend API             Simulation Engine

     │                      │                        │

     └───────────────┬──────┴───────────────┬────────┘

                     │                      │

               PostgreSQL           Observability Stack

                                         │

                     ┌───────────┬────────────┬───────────┐

                     │           │            │

               Prometheus      Loki        Tempo

                     │

                 Grafana

```

The AI Research Environment executes independently and connects through exported datasets and public APIs.

SPEC-012 does not add a model-serving runtime to the Backend API. Training and inference execute in
the independent AI Research Environment. The planned Prediction Component is part of the Backend
API deployment and stores only accepted publication metadata and buckets in PostgreSQL.

---

# 4. Runtime Containers

The platform consists of the following executable containers.

---

## Web Application

Technology:

* React
* TypeScript
* Vite

Responsibilities:

* user interface;
* dashboards;
* administration;
* experiment visualization.

---

## Backend API

Technology:

* Python
* FastAPI

Responsibilities:

* business logic;
* REST APIs;
* event publication;
* authentication;
* dataset export.

---

## PostgreSQL

Responsibilities:

* transactional persistence;
* event persistence;
* telemetry persistence;
* analytical persistence.

---

## Digital Twin Simulation Engine

Responsibilities:

* synthetic users;
* synthetic vehicles;
* synthetic telemetry;
* synthetic reservations;
* scenario execution.

The Simulation Engine is intentionally deployed independently.

---

## Observability Stack

Components:

* Prometheus
* Grafana
* Loki
* Tempo
* OpenTelemetry Collector

Responsibilities:

* metrics;
* logs;
* traces;
* dashboards.

---

## Notification Mock

Responsibilities:

* simulate notification delivery;
* support future replacement by external providers.

---

# 5. Runtime Communication

Communication follows strict architectural boundaries.

| Source                  | Destination               | Protocol              |
| ----------------------- | ------------------------- | --------------------- |
| Web Application         | Backend API               | HTTPS / REST          |
| Simulation Engine       | Backend API               | HTTPS / REST          |
| Backend API             | PostgreSQL                | SQL                   |
| Backend API             | Notification Mock         | HTTP                  |
| Backend API             | OpenTelemetry Collector   | OTLP                  |
| Prometheus              | Backend API               | HTTP Metrics          |
| Grafana                 | Prometheus / Loki / Tempo | Native APIs           |
| AI Research Environment | Backend API               | REST / Dataset Export |

Direct database access by external systems is prohibited.

The AI Research Environment downloads authorized Dataset Export artifacts and publishes complete
Weekly Occupancy Prediction profiles through HTTPS. It shall not mount Dataset Export storage or
connect directly to PostgreSQL.

---

# 6. Docker Compose Topology

The reference environment consists of the following services.

```yaml
Frontend

Backend API

PostgreSQL

Simulation Engine

Notification Mock

Prometheus

Grafana

Loki

Tempo

OpenTelemetry Collector
```

Every service shall be independently replaceable.

---

# 7. Startup Sequence

The recommended startup order is:

```text
PostgreSQL

↓

Backend API

↓

Observability Stack

↓

Frontend

↓

Simulation Engine

↓

AI Research Environment
```

This sequence guarantees that dependent services become available before application initialization.

---

# 8. Networking

All runtime containers execute within an isolated Docker network.

Characteristics:

* internal service discovery;
* private communication;
* exposed public ports only when required;
* container name resolution.

Example:

```text
frontend

↓

backend-api

↓

postgres

↓

otel-collector

↓

grafana
```

No component should depend on fixed IP addresses.

---

# 9. Configuration Strategy

Configuration shall follow the **Twelve-Factor App** principles whenever applicable.

Configuration sources include:

* environment variables;
* `.env` files (development only);
* Docker Compose configuration.

Configuration values include:

* database connection;
* JWT secret;
* logging level;
* telemetry endpoints;
* API URLs;
* simulation parameters.

Configuration shall never be hardcoded.

---

# 10. Secrets Management

Secrets shall remain outside the source code repository.

Examples:

* JWT secret;
* database password;
* API credentials;
* external service tokens.

Development environments may use local `.env` files.

Future production environments should integrate dedicated secret management solutions.

---

# 11. Persistent Storage

Persistent Docker volumes shall be created for:

* PostgreSQL;
* Grafana configuration;
* Loki storage;
* Tempo traces;
* Dataset Export artifacts when local artifact storage is enabled.

Version 1 Dataset Export may use a mounted persistent volume through its artifact-storage
abstraction. Artifact bytes remain outside the application image and PostgreSQL. Future deployments
may replace the mounted volume with object storage without changing the REST contract.

Application processes should otherwise remain stateless.

This enables future horizontal scaling.

---

# 12. Infrastructure as Code

The complete runtime environment shall be defined as code.

Infrastructure artifacts include:

* Dockerfiles;
* Docker Compose;
* Makefile;
* environment templates.

Infrastructure configuration shall be version controlled together with application code.

---

# 13. Local Development Workflow

The expected workflow is:

```text
Clone Repository

↓

Configure .env

↓

docker compose up

↓

Database Migration

↓

Platform Ready

↓

Run Simulations

↓

Generate Datasets

↓

Train Models

↓

Evaluate Results
```

No manual infrastructure installation should be necessary.

---

# 14. Continuous Integration

Every Pull Request shall execute an automated pipeline.

Typical stages include:

```text
Checkout

↓

Install Dependencies

↓

Formatting

↓

Linting

↓

Static Analysis

↓

Unit Tests

↓

Integration Tests

↓

Coverage

↓

Security Scan

↓

Docker Build

↓

Artifact Publication
```

Deployment to production is intentionally excluded from the MVP.

---

# 15. Continuous Delivery Evolution

Although not required initially, the architecture supports future deployment automation.

Possible future pipeline:

```text
Pull Request

↓

CI Validation

↓

Merge

↓

Container Registry

↓

Staging

↓

Production
```

This evolution should not require architectural changes.

---

# 16. Runtime Scalability

The MVP executes as a single Backend API instance.

Future evolution may include:

* multiple Backend API replicas;
* dedicated event broker;
* separated analytics database;
* distributed simulation workers;
* cloud-native orchestration.

The chosen Modular Monolith architecture allows this evolution without affecting business logic.

---

# 17. Failure Strategy

The runtime environment should tolerate failures gracefully.

Examples:

Database unavailable:

* API reports degraded health;
* requests fail gracefully.

Simulation failure:

* operational platform remains available.

Observability unavailable:

* business execution continues;
* telemetry loss is acceptable during development.

Notification failure:

* business transaction remains successful;
* notification failure is logged.

---

# 18. Deployment Environments

The platform supports three logical environments.

## Development

Purpose:

Local development.

Characteristics:

* Docker Compose;
* local PostgreSQL;
* mocked notifications.

---

## Research

Purpose:

Experiment execution.

Characteristics:

* reproducible simulations;
* dataset generation;
* observability enabled.

---

## Future Production

Purpose:

Operational deployment.

Potential improvements:

* Kubernetes;
* managed PostgreSQL;
* external notification providers;
* cloud monitoring;
* horizontal scaling.

This environment is outside the scope of the current project.

---

# 19. Relationship with Other Documents

This document depends on:

* `001-architecture-vision.md`
* `003-container-diagram.md`
* `004-component-diagram-backend.md`
* `006-quality-attributes.md`
* `007-observability-view.md`

Future ADRs shall reference this document whenever deployment decisions are involved.

---

# 20. Architectural Decisions Supported

This document reinforces the following architectural decisions:

* containerized execution;
* reproducible development environment;
* stateless application services;
* external Simulation Engine;
* external AI Research Environment;
* centralized observability;
* infrastructure as code.

These decisions directly support the quality attributes defined in **Architecture View 006 —
Quality Attributes**.

---

# 21. Future Evolution

The deployment architecture was intentionally designed to support gradual evolution.

Possible future enhancements include:

* Kubernetes orchestration;
* service mesh;
* distributed event brokers;
* object storage for datasets;
* Feature Store for Machine Learning;
* cloud-native monitoring;
* GitOps deployment;
* autoscaling simulation workers.

These enhancements can be introduced incrementally without requiring significant changes to the platform architecture.

---

# 22. Final Considerations

The Deployment Runtime View concludes the architectural definition of the Smart Charging Experimentation Platform.

Together with the previous architectural specifications, it establishes a complete description of the platform from multiple complementary perspectives:

* **Vision** defines why the platform exists.
* **Context** defines its relationship with external actors and systems.
* **Containers** describe the executable units.
* **Components** define the internal organization of the Backend API.
* **Data View** explains how information flows and is owned.
* **Quality Attributes** establish the non-functional drivers of the architecture.
* **Observability View** defines how runtime behavior is measured and analyzed.
* **Deployment Runtime View** describes how the platform is executed and reproduced.

This architectural foundation provides a consistent basis for the next phase of the project, which consists of documenting the Architecture Decision Records (ADRs), defining functional specifications and implementing the Smart Charging Experimentation Platform.
