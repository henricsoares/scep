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

frontend/               # React demonstration dashboard

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
* Identity and Access specification: `docs/specs/SPEC-005-identity-and-access.md`
* Reservations specification: `docs/specs/SPEC-006-reservations.md`
* Charging Sessions specification: `docs/specs/SPEC-007-charging-sessions.md`
* Telemetry specification: `docs/specs/SPEC-008-telemetry.md`
* Domain Events specification: `docs/specs/SPEC-009-domain-events.md`
* Analytics specification: `docs/specs/SPEC-010-analytics.md`
* Dataset Export specification: `docs/specs/SPEC-011-dataset-export.md`
* Weekly Occupancy Predictions specification: `docs/specs/SPEC-012-predictions.md`
* Digital Twin Simulation Engine specification: `docs/specs/SPEC-013-simulation-engine.md`
* External Simulation Engine decision: `docs/architecture/decisions/ADR-005-external-simulation-engine.md`

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

The Web Application is a thin, authenticated demonstration client with Overview, Infrastructure,
Analytics and Weekly Occupancy Predictions views. It consumes public Backend APIs and does not
reimplement authorization, analytical formulas or prediction logic. See `frontend/README.md` for
standalone development and validation commands.

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
make test
make test-unit
make backend-lint
make backend-typecheck
make backend-security
make precommit
make ci
```

`make test` is the deterministic full-suite command. It starts the Docker Compose PostgreSQL
service, recreates the dedicated `scep_test` database, applies all Alembic migrations, exports the
test database URLs and runs every backend test. It never drops or recreates the normal local `scep`
database. The test database and a PostgreSQL container started by the command are removed when the
run finishes. When the root `.env` is absent, the runner creates a temporary copy from
`.env.example` and removes it during cleanup; an existing `.env` is never replaced or removed.

`make test-unit` is the lightweight path. It runs only tests under `backend/tests/unit` and does not
require PostgreSQL. PostgreSQL integration, migration, concurrency and snapshot tests are covered
by `make test` and `make ci`.

Running `pytest` directly is intended only for focused tests whose database dependencies have
already been prepared explicitly.

A manual migration command is still available for development and troubleshooting:

```bash
make migrate
```

However, migrations are normally executed automatically when the backend container starts.

---

## Implemented Business Capabilities

The current domain includes Identity, Facilities, Charging Stations, Connectors, Vehicles,
Reservations, Charging Sessions, Telemetry, Domain Events, Analytics, Dataset Export and the
backend-visible SimulationRun context. SPEC-013 is implemented by an external deterministic
simulator that uses only public APIs and preserves normal non-simulated behavior.

### Identity and Access

The platform currently supports Authenticated Identities for Human and Technical Client accounts,
static Role/profile-to-capability authorization, and Facility-scoped access for Facility
Operators. `Researcher` manages Simulation Runs; `DataScientist` and explicitly profiled AI
Research Technical Clients use only their own single-Facility Research Dataset Exports and the
future prediction-publisher capability.

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

### Vehicles and Reservations

The platform currently supports owned Vehicles, Reservation scheduling for Connectors and
Charging Sessions, including lifecycle management, conflict prevention, cancellation, rescheduling
and No-Show handling. Every Charging Session defined by SPEC-007 originates from exactly one
Reservation; direct or unreserved Charging Sessions remain out of scope.

### Telemetry

The platform supports immutable TelemetrySamples for active or completed Charging Sessions,
including single and atomic batch ingestion, idempotency and authorized retrieval.

### Domain Events, Analytics and Dataset Export

The platform transactionally persists Domain Events, exposes authenticated read-only Analytics
over operational data, and produces CSV or Parquet Dataset Export artifacts with snapshot,
integrity, provenance and retention metadata.

### Digital Twin Simulation Engine

SPEC-013 Version 1 provides an independently executable external simulator plus a restricted
backend `SimulationRun` lifecycle. Administrators provision dedicated Users, Vehicles and
infrastructure; the simulator generates deterministic Reservation, Charging Session and Telemetry
behavior with logical time, run-scoped authorization, provenance, idempotency, checkpointing and
execution reports. The engine never imports backend modules or connects directly to PostgreSQL.

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

**SCEP v1.0 Research Platform MVP complete**

Completed:

* ✅ Architecture Specifications
* ✅ Architecture Decision Records (ADRs)
* ✅ Repository Governance
* ✅ SPEC-001 — Project Foundation
* ✅ SPEC-002 — Domain Model and Ubiquitous Language
* ✅ SPEC-003 — Facilities
* ✅ SPEC-004 — Charging Stations
* ✅ SPEC-005 — Identity and Access
* ✅ SPEC-006 — Reservations
* ✅ SPEC-007 — Charging Sessions
* ✅ SPEC-008 — Telemetry
* ✅ SPEC-009 — Domain Events
* ✅ SPEC-010 — Analytics
* ✅ SPEC-011 — Dataset Export: Approved and implemented
* ✅ SPEC-012 — Weekly Occupancy Predictions: Approved and implemented
* ✅ SPEC-013 — Digital Twin Simulation Engine: Approved and implemented
* ✅ Minimal Web Dashboard — Overview, Infrastructure, Analytics and Predictions

The external reference baseline used the completed 10-week `ANALYTICAL_OCCUPANCY` training export
and two-week holdout while keeping feature engineering, evaluation and inference outside the
Backend API.

---

## License

This repository is maintained for academic and research purposes.
