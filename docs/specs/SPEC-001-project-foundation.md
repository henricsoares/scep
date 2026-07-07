# SPEC-001 — Project Foundation

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved
**Version:** 1.0
**Document Owner:** Project Team
**Last Update:** 2026

---

# 1. Purpose

This specification defines the technical foundation of the Smart Charging Experimentation Platform (SCEP).

Its goal is to establish the initial project structure, development tooling, runtime environment, quality gates and engineering conventions required before implementing business capabilities.

After this specification is implemented, the repository must provide a professional but lightweight foundation for all future features.

---

# 2. Goals

The project foundation must provide:

* reproducible local development;
* backend project structure;
* frontend project structure;
* external simulation engine structure;
* research workspace structure;
* Docker Compose environment;
* PostgreSQL integration;
* Alembic migration support;
* automated quality tooling;
* GitHub Actions CI;
* observability stack;
* initial health endpoints;
* documentation conventions.

---

# 3. Non-Goals

This specification does not implement:

* user authentication;
* authorization rules;
* charging station management;
* reservations;
* charging sessions;
* telemetry ingestion;
* dataset export;
* AI model training;
* real notification delivery.

These capabilities will be specified in later documents.

---

# 4. Repository Structure

The repository shall follow this structure:

```text
scep/
├── backend/
├── frontend/
├── simulation-engine/
├── research/
│   ├── notebooks/
│   ├── datasets/
│   ├── experiments/
│   └── models/
├── docs/
│   ├── architecture/
│   └── specs/
├── docker/
├── scripts/
├── .github/
│   └── workflows/
├── docker-compose.yml
├── Makefile
├── README.md
└── LICENSE
```

---

# 5. Backend Foundation

The backend shall be implemented using:

* Python 3.13;
* FastAPI;
* uv;
* SQLAlchemy;
* Alembic;
* Pydantic.

Initial backend structure:

```text
backend/
├── app/
│   ├── api/
│   ├── core/
│   ├── infrastructure/
│   ├── modules/
│   │   ├── identity/
│   │   ├── charging/
│   │   ├── telemetry/
│   │   ├── analytics/
│   │   ├── prediction/
│   │   ├── datasets/
│   │   ├── events/
│   │   └── notification/
│   ├── shared/
│   └── main.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── architecture/
├── alembic/
├── pyproject.toml
├── uv.lock
└── Dockerfile
```

---

# 6. Backend Initial Capabilities

The backend shall initially expose:

```text
GET /health
GET /health/live
GET /health/ready
```

Initial behavior:

* `/health` returns general application status;
* `/health/live` returns liveness status;
* `/health/ready` verifies database connectivity.

No business endpoint is required in this specification.

---

# 7. Backend Configuration

Configuration shall use environment variables.

Required initial variables:

```text
APP_NAME
APP_ENV
APP_VERSION
DATABASE_URL
LOG_LEVEL
JWT_SECRET
OTEL_EXPORTER_OTLP_ENDPOINT
```

A `.env.example` file shall be provided.

Secrets must not be committed.

---

# 8. Database Foundation

PostgreSQL shall be available through Docker Compose.

The backend shall connect to PostgreSQL using SQLAlchemy.

Alembic shall be configured from the beginning.

The first migration may be empty, serving only to validate the migration infrastructure.

Required command:

```text
make migrate
```

---

# 9. Frontend Foundation

The frontend shall be implemented using:

* React;
* TypeScript;
* Vite.

Initial structure:

```text
frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── hooks/
│   ├── types/
│   └── main.tsx
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

Initial frontend behavior:

* render a basic SCEP landing page;
* call `/health` from the Backend API;
* display backend health status.

The frontend is not the main research artifact, but it must support platform demonstration and experimentation workflows.

---

# 10. Simulation Engine Foundation

The Simulation Engine shall be a separate application.

Initial structure:

```text
simulation-engine/
├── app/
│   ├── core/
│   ├── scenarios/
│   ├── clients/
│   └── main.py
├── tests/
├── pyproject.toml
├── uv.lock
└── Dockerfile
```

Initial behavior:

* start successfully;
* read configuration from environment variables;
* call Backend API `/health`;
* log connection status.

No simulation scenario is required in this specification.

---

# 11. Research Workspace

The research directory shall support AI and dataset experimentation.

Initial structure:

```text
research/
├── notebooks/
├── datasets/
├── experiments/
└── models/
```

Each directory shall contain a `.gitkeep` file.

Large generated datasets and trained models should not be committed unless explicitly required.

---

# 12. Docker Compose Environment

`docker compose up` shall start the complete local environment.

Required services:

* backend;
* frontend;
* simulation-engine;
* postgres;
* prometheus;
* grafana;
* loki;
* tempo;
* otel-collector.

The environment should be usable locally without cloud dependencies.

---

# 13. Observability Foundation

The observability stack shall be available from the beginning.

Initial requirements:

* backend emits structured logs;
* backend exposes metrics endpoint;
* OpenTelemetry configuration exists;
* Prometheus configuration exists;
* Grafana container starts;
* Loki container starts;
* Tempo container starts.

Full dashboard implementation is not required in this specification.

---

# 14. Quality Tooling

The backend shall use:

* Ruff;
* Black;
* MyPy;
* pytest;
* pytest-asyncio;
* Coverage.py;
* Bandit;
* pip-audit.

Minimum coverage target:

```text
80%
```

Initial tests may validate:

* application startup;
* health endpoints;
* database readiness;
* configuration loading.

---

# 15. Pre-Commit

The project shall include pre-commit hooks for:

* formatting;
* linting;
* type checking where practical;
* basic security checks.

Developers should be able to run:

```text
make precommit
```

---

# 16. GitHub Actions CI

A GitHub Actions workflow shall be created.

Minimum pipeline stages:

```text
Checkout
Install uv
Install dependencies
Run formatting check
Run lint
Run type check
Run tests
Run coverage
Run security scan
Run dependency audit
Build Docker images
```

The pipeline must run on:

* pull requests;
* pushes to `main`.

---

# 17. Makefile Commands

The project shall provide a root `Makefile`.

Required commands:

```text
make up
make down
make logs
make backend-test
make backend-lint
make backend-format
make backend-typecheck
make backend-security
make migrate
make ci
```

Optional commands may be added later.

---

# 18. Licensing

The project shall use the **MIT License**.

Rationale:

* simple;
* permissive;
* suitable for academic and portfolio use;
* compatible with future reuse.

A `LICENSE` file shall be included at repository root.

---

# 19. Git Workflow

The project shall follow **GitHub Flow**.

Rules:

* `main` is the stable branch;
* development happens in feature branches;
* Pull Requests are used for meaningful changes;
* direct commits to `main` should be avoided when practical.

Commit messages should follow **Conventional Commits**.

Examples:

```text
feat: add backend health endpoints
fix: correct database readiness check
docs: update architecture documentation
test: add health endpoint tests
chore: configure CI pipeline
```

---

# 20. Definition of Done

This specification is complete when:

* repository structure exists;
* backend starts successfully;
* frontend starts successfully;
* simulation engine starts successfully;
* PostgreSQL starts through Docker Compose;
* observability containers start through Docker Compose;
* backend exposes health endpoints;
* backend connects to PostgreSQL;
* Alembic is configured;
* first migration exists;
* quality tooling is configured;
* GitHub Actions CI exists;
* root README references architecture and specs;
* MIT license is included.

---

# 21. Acceptance Criteria

The following commands shall work successfully:

```text
docker compose up
make backend-test
make backend-lint
make backend-typecheck
make backend-security
make migrate
make ci
```

Expected results:

* all containers start;
* backend health endpoint responds;
* frontend can reach backend;
* simulation engine can reach backend;
* tests pass;
* lint passes;
* type checking passes;
* security checks pass;
* migrations run successfully.

---

# 22. Future Specifications

This foundation enables the following upcoming specifications:

* Identity and Access;
* Smart Charging Domain;
* Charging Stations;
* Reservations;
* Charging Sessions;
* Telemetry;
* Domain Events;
* Analytics;
* Dataset Export;
* Prediction;
* Digital Twin Simulation Engine.

---

# 23. Final Considerations

This specification intentionally balances professional engineering practices with implementation feasibility.

The objective is not to create unnecessary process overhead, but to establish a stable foundation that prevents rework and supports future development.

Once implemented, this foundation becomes the baseline for all subsequent functional specifications.
