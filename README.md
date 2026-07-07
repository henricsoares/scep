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
                         │
                         ▼
                 Backend API
              (Modular Monolith)
                         │
         ┌───────────────┼────────────────┐
         │               │                │
         ▼               ▼                ▼
   PostgreSQL      Domain Events    Observability

External Systems

• Digital Twin Simulation Engine
• AI Research Environment
• Notification Mock
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

```
docs/architecture/
```

Functional specifications are located in:

```
docs/specs/
```

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

- ✅ Architecture Specifications
- ✅ Architecture Decision Records (ADRs)

Next Steps:

- Functional Specifications
- Backend Implementation
- Digital Twin Simulation Engine
- AI Experiments

---

## License

This repository is maintained for academic and research purposes.