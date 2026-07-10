# Smart Charging Experimentation Platform (SCEP)

> A research-oriented platform for Smart Charging, Software Engineering, IoT and Artificial Intelligence.

---

## Overview

The **Smart Charging Experimentation Platform (SCEP)** is a postgraduate research project that combines modern Software Engineering practices with Artificial Intelligence and IoT.

Unlike conventional charging management systems, SCEP is designed as an **experimentation platform**, enabling researchers and software engineers to:

* simulate realistic Smart Charging scenarios;
* generate reproducible datasets;
* evaluate architectural decisions;
* develop and validate AI models;
* study observability and software quality;
* experiment with modern software engineering practices.

Electric vehicle charging management is used as the first application domain, serving as a realistic case study.

---

## Objectives

SCEP aims to demonstrate the integration of:

* Modern Software Engineering
* Software Architecture
* Domain-Driven Design
* Event-Driven Architecture
* Artificial Intelligence
* Data Engineering
* IoT
* DevSecOps
* Observability
* Quality Engineering

within a single research platform.

---

## High-Level Architecture

```text
                  Web Application
                         |
                         v
                 Backend API
              (Modular Monolith)
                         |
         +---------------+----------------+
         |               |                |
         v               v                v
   PostgreSQL      Domain Events    Observability

External Systems

* Digital Twin Simulation Engine
* AI Research Environment
* Notification Mock
```

---

## Repository Structure

```text
docs/
    architecture/
    specs/

backend/

frontend/

simulation-engine/

docker/
```

---

## Documentation

Architecture documentation can be found under:

```text
docs/architecture/
```

Functional specifications are located in:

```text
docs/specs/
```

Key documents:

* Architecture vision: `docs/architecture/001-architecture-vision.md`
* Container diagram: `docs/architecture/003-container-diagram.md`
* Backend component diagram: `docs/architecture/004-component-diagram-backend.md`
* Quality attributes: `docs/architecture/006-quality-attributes.md`
* Runtime view: `docs/architecture/008-deployment-runtime-view.md`
* Project foundation specification: `docs/specs/SPEC-001-project-foundation.md`
* Domain model specification: `docs/specs/SPEC-002-domain-model-and-ubiquitous-language.md`
* Facilities specification: `docs/specs/SPEC-003-facilities.md`
* Charging Stations specification: `docs/specs/SPEC-004-charging-stations.md`

---

## Technology Stack

### Backend

* Python 3.13
* FastAPI
* SQLAlchemy
* Alembic
* PostgreSQL

### Frontend

* React
* TypeScript
* Vite

### Infrastructure

* Docker Compose
* OpenTelemetry
* Prometheus
* Grafana
* Loki
* Tempo

### Artificial Intelligence

* Python
* Jupyter Notebook
* Pandas
* Scikit-Learn
* XGBoost (future)
* PyTorch (future)

---

## Local Development

### Prerequisites

Install the following tools before starting the platform:

* Git
* Docker
* Docker Compose
* Make

### First Run

Clone the repository and enter the project directory:

```bash
git clone https://github.com/henricsoares/scep.git
cd scep
```

Create the local environment file:

```bash
cp .env.example .env
```

The `.env` file is required for local configuration and is intentionally ignored by Git.

Start the complete platform:

```bash
make up
```

The backend automatically executes all pending Alembic migrations before starting the API. No manual migration command is required during the normal Docker Compose startup flow.

### Local Services

After startup, the main services are available at:

| Service        | URL                                  |
| -------------- | ------------------------------------ |
| Backend API    | `http://localhost:8000`              |
| Swagger UI     | `http://localhost:8000/docs`         |
| OpenAPI schema | `http://localhost:8000/openapi.json` |
| Frontend       | `http://localhost:5173`              |
| Prometheus     | `http://localhost:9090`              |
| Grafana        | `http://localhost:3000`              |

The Docker Compose environment starts:

* Backend API
* Frontend
* Simulation Engine
* PostgreSQL
* Prometheus
* Grafana
* Loki
* Tempo
* OpenTelemetry Collector

### Environment Status

Check the running containers:

```bash
docker compose ps
```

Inspect backend logs:

```bash
docker compose logs -f backend
```

Check the current Alembic revision:

```bash
docker compose exec -T backend uv run alembic current
```

### Stop the Platform

Stop the containers while preserving local data:

```bash
make down
```

To remove the containers and database volumes:

```bash
docker compose down -v
```

### Quality and Development Commands

```bash
make backend-test
make backend-lint
make backend-typecheck
make backend-security
make precommit
make ci
```

A manual migration command is still available for development and troubleshooting:

```bash
make migrate
```

However, migrations are normally executed automatically when the backend container starts.

---

## Implemented Business Capabilities

### Facilities

The platform currently supports:

* creation and listing of Facilities;
* retrieval and update of Facilities;
* Facility status management;
* geographical and timezone validation;
* historical preservation through deactivation instead of deletion.

### Charging Stations and Connectors

The platform currently supports:

* creation of Charging Stations inside active Facilities;
* creation of one or more Connectors with a Station;
* listing Stations by Facility;
* retrieval of Stations with their Connectors;
* partial Station updates;
* Station operational-status management;
* addition of Connectors to existing Stations;
* Connector-status management;
* validation of supported Connector types;
* unique Station serial numbers;
* historical preservation without physical deletion.

The currently supported Connector types are:

* CCS2
* CHAdeMO
* NACS
* Type 2

---

## Research Focus

Current research topics include:

* Smart Charging
* Charging Station Occupancy Prediction
* Synthetic Data Generation
* Event-Driven Architectures
* Software Observability
* AI-ready Software Platforms

---

## Project Status

Current Phase:

**Business Domain Implementation**

Completed:

* ✅ Architecture Specifications
* ✅ Architecture Decision Records (ADRs)
* ✅ Repository Governance
* ✅ SPEC-001 — Project Foundation
* ✅ SPEC-002 — Domain Model and Ubiquitous Language
* ✅ SPEC-003 — Facilities
* ✅ SPEC-004 — Charging Stations

Next Steps:

* SPEC-005 — Identity and Access
* Reservations
* Charging Sessions
* Telemetry
* Analytics
* Digital Twin Simulation Engine
* AI Experiments

---

## License

This repository is maintained for academic and research purposes.
