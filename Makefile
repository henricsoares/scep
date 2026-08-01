.PHONY: up down logs backend-test backend-test-unit backend-lint backend-format backend-typecheck backend-security format lint typecheck test test-unit migrate ci precommit

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend-test: test

backend-test-unit: test-unit

backend-lint:
	cd backend && uv run ruff check app tests && uv run black --check app tests

backend-format:
	cd backend && uv run ruff check --fix app tests && uv run black app tests

backend-typecheck:
	cd backend && uv run mypy app tests

format: backend-format

lint: backend-lint

typecheck: backend-typecheck

test:
	./scripts/run-backend-tests.sh test

test-unit:
	cd backend && OTEL_SDK_DISABLED=true uv run pytest tests/unit

backend-security:
	cd backend && uv run bandit -c pyproject.toml -r app && uv run pip-audit

migrate:
	cd backend && uv run alembic upgrade head

precommit:
	uv run --project backend pre-commit run --all-files

ci: backend-lint backend-typecheck
	./scripts/run-backend-tests.sh coverage
	cd backend && uv run bandit -c pyproject.toml -r app && uv run pip-audit
