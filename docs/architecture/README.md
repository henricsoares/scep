# Architecture Documentation

This directory contains the architectural documentation for the **Smart Charging Experimentation Platform (SCEP)**.

The documentation follows a specification-driven approach.

The architecture is considered the project's baseline and should evolve only through new Architecture Decision Records (ADRs).

---

# Architecture Documents

## SPEC-001 — Architecture Vision

Defines the purpose, motivation and overall architectural vision of SCEP.

File:

```
001-architecture-vision.md
```

---

## SPEC-002 — Context Diagram

C4 Model – Level 1

Describes:

- actors;
- external systems;
- platform boundaries.

File:

```
002-context-diagram.md
```

---

## SPEC-003 — Container Diagram

C4 Model – Level 2

Defines the deployable units composing the platform.

File:

```
003-container-diagram.md
```

---

## SPEC-004 — Backend Component Diagram

C4 Model – Level 3

Describes the internal organization of the Backend API.

File:

```
004-component-diagram-backend.md
```

---

## SPEC-005 — Data View

Describes:

- data ownership;
- data lifecycle;
- domain events;
- research datasets;
- AI readiness.

File:

```
005-data-view.md
```

---

## SPEC-006 — Quality Attributes

Defines the architectural quality attributes that drive all technical decisions.

Examples:

- Maintainability
- Extensibility
- Reproducibility
- Testability
- Observability

File:

```
006-quality-attributes.md
```

---

## SPEC-007 — Observability View

Defines the observability architecture adopted by SCEP.

Topics include:

- logs;
- metrics;
- traces;
- health monitoring.

File:

```
007-observability-view.md
```

---

## SPEC-008 — Deployment Runtime View

Describes the runtime topology and deployment architecture.

Topics include:

- Docker Compose;
- containers;
- networking;
- infrastructure services.

File:

```
008-deployment-runtime-view.md
```

---

# Architecture Decision Records (ADRs)

Architectural decisions are documented separately.

Location:

```
decisions/
```

Current ADRs:

| ADR | Decision |
|------|----------|
| ADR-001 | Modular Monolith |
| ADR-002 | Python + FastAPI |
| ADR-003 | Event-Driven Architecture |
| ADR-004 | PostgreSQL |
| ADR-005 | External Digital Twin Simulation Engine |
| ADR-006 | Observability-First |
| ADR-007 | DevSecOps + Continuous Integration |
| ADR-008 | AI Research Environment |

---

# Architectural Principles

The architecture follows the following principles:

- API First
- Modular Monolith
- Event-Driven Design
- Domain-Driven Design
- Clean Architecture
- Security by Design
- Observability by Design
- DevSecOps
- Reproducible Research

---

# Current Status

**Architecture Baseline v1.0**

The architecture is considered stable.

Future architectural changes should be introduced through new ADRs instead of directly modifying the baseline documents whenever possible.