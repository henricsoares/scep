# Smart Charging Experimentation Platform (SCEP)

> A research-oriented platform for Smart Charging, Software Engineering, IoT and Artificial Intelligence.

---

## Overview

The **Smart Charging Experimentation Platform (SCEP)** is a postgraduate research project that combines modern Software Engineering practices with Artificial Intelligence and IoT.

Unlike conventional charging management systems, SCEP is designed as an **experimentation platform**, enabling researchers and software engineers to:

- simulate realistic Smart Charging scenarios;
- generate reproducible datasets;
- evaluate architectural decisions;
- develop and validate AI models;
- study observability and software quality;
- experiment with modern software engineering practices.

Electric vehicle charging management is used as the first application domain, serving as a realistic case study.

---

## Objectives

SCEP aims to demonstrate the integration of:

- Modern Software Engineering
- Software Architecture
- Domain-Driven Design
- Event-Driven Architecture
- Artificial Intelligence
- Data Engineering
- IoT
- DevSecOps
- Observability
- Quality Engineering

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

- Architecture vision: `docs/architecture/001-architecture-vision.md`
- Container diagram: `docs/architecture/003-container-diagram.md`
- Backend component diagram: `docs/architecture/004-component-diagram-backend.md`
- Quality attributes: `docs/architecture/006-quality-attributes.md`
- Runtime view: `docs/architecture/008-deployment-runtime-view.md`
- Project foundation specification: `docs/specs/SPEC-001-project-foundation.md`

---

## Technology Stack

### Backend

- Python 3.13
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL

### Frontend

- React
- TypeScript
- Vite

### Infrastructure

- Docker Compose
- OpenTelemetry
- Prometheus
- Grafana
- Loki
- Tempo

### Artificial Intelligence

- Python
- Jupyter Notebook
- Pandas
- Scikit-Learn
- XGBoost (future)
- PyTorch (future)

---

## Local Development

Copy `.env.example` to `.env` for local overrides, then start the platform:

```bash
make up
```

Useful commands:

```bash
make backend-test
make backend-lint
make backend-typecheck
make backend-security
make migrate
make precommit
make ci
```

`docker-compose.yml` starts the backend, frontend, simulation engine, PostgreSQL, Prometheus, Grafana, Loki, Tempo and OpenTelemetry Collector.

---

## Research Focus

Current research topics include:

- Smart Charging
- Charging Station Occupancy Prediction
- Synthetic Data Generation
- Event-Driven Architectures
- Software Observability
- AI-ready Software Platforms

---

## Project Status

Current Phase:

**Architecture Baseline v1.0**

Completed:

- Architecture Specifications
- Architecture Decision Records (ADRs)
- SPEC-001 project foundation

Next Steps:

- Functional Specifications
- Backend Implementation
- Digital Twin Simulation Engine
- AI Experiments

---

## License

This repository is maintained for academic and research purposes.
