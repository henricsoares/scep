.PHONY: up down logs backend-test backend-test-unit backend-lint backend-format backend-typecheck backend-security simulation-test simulation-lint simulation-format format lint typecheck test test-unit migrate ci precommit

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend-test:
	./scripts/run-backend-tests.sh test

backend-test-unit:
	cd backend && OTEL_SDK_DISABLED=true uv run pytest tests/unit

backend-lint:
	cd backend && uv run ruff check app tests && uv run black --check app tests

backend-format:
	cd backend && uv run ruff check --fix app tests && uv run black app tests

backend-typecheck:
	cd backend && uv run mypy app tests

simulation-test:
	cd simulation-engine && PYTHONPATH=. uv run pytest -q

simulation-lint:
	cd simulation-engine && uv run ruff check app tests && uv run black --check app tests

simulation-format:
	cd simulation-engine && uv run ruff check --fix app tests && uv run black app tests

format: backend-format simulation-format

lint: backend-lint simulation-lint

typecheck: backend-typecheck

test: backend-test simulation-test

test-unit: backend-test-unit simulation-test

backend-security:
	cd backend && uv run bandit -c pyproject.toml -r app && uv run pip-audit

migrate:
	cd backend && uv run alembic upgrade head

precommit:
	uv run --project backend pre-commit run --all-files

ci: lint backend-typecheck
	./scripts/run-backend-tests.sh coverage
	$(MAKE) simulation-test
	cd backend && uv run bandit -c pyproject.toml -r app && uv run pip-audit
