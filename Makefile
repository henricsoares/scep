.PHONY: up down logs backend-test backend-lint backend-format backend-typecheck backend-security format lint typecheck test migrate ci precommit

CI_DATABASE_URL ?= postgresql+psycopg://scep:scep@localhost:5432/scep

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend-test:
	cd backend && uv run pytest

backend-lint:
	cd backend && uv run ruff check app tests && uv run black --check app tests

backend-format:
	cd backend && uv run ruff check --fix app tests && uv run black app tests

backend-typecheck:
	cd backend && uv run mypy app tests

format: backend-format

lint: backend-lint

typecheck: backend-typecheck

test: backend-test

backend-security:
	cd backend && uv run bandit -c pyproject.toml -r app && uv run pip-audit

migrate:
	cd backend && uv run alembic upgrade head

precommit:
	uv run --project backend pre-commit run --all-files

ci: export DATABASE_URL := $(CI_DATABASE_URL)
ci: export POSTGRES_TEST_DATABASE_URL := $(CI_DATABASE_URL)
ci: export OTEL_SDK_DISABLED := true
ci: backend-lint backend-typecheck
	@postgres_was_running="$$(docker compose ps --status running -q postgres)"; \
	cleanup() { \
		status=$$?; \
		trap - EXIT INT TERM; \
		if [ -z "$$postgres_was_running" ]; then docker compose rm --stop --force postgres; fi; \
		exit $$status; \
	}; \
	trap cleanup EXIT INT TERM; \
	set -eu; \
	docker compose up -d --wait postgres; \
	cd backend; \
	uv run alembic upgrade head; \
	uv run coverage run -m pytest; \
	uv run coverage report; \
	uv run bandit -c pyproject.toml -r app; \
	uv run pip-audit
