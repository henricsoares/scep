# Smart Charging Experimentation Platform (SCEP)

SCEP is a research-oriented platform for smart EV charging experimentation. The foundation follows the approved architecture and SPEC-001 project structure.

## Architecture and specifications

- Architecture vision: `docs/architecture/001-architecture-vision.md`
- Container diagram: `docs/architecture/003-container-diagram.md`
- Backend component diagram: `docs/architecture/004-component-diagram-backend.md`
- Quality attributes: `docs/architecture/006-quality-attributes.md`
- Runtime view: `docs/architecture/008-deployment-runtime-view.md`
- Project foundation specification: `docs/specs/SPEC-001-project-foundation.md`

## Local development

Copy `.env.example` to `.env` for local overrides, then run:

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
make ci
```

## Containers

`docker-compose.yml` starts the backend, frontend, simulation engine, PostgreSQL, Prometheus, Grafana, Loki, Tempo, and OpenTelemetry Collector.
