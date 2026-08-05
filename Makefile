.PHONY: up down logs backend-test backend-test-unit backend-lint backend-format backend-typecheck backend-security frontend-test frontend-typecheck frontend-build frontend-audit simulation-test simulation-lint simulation-format research-test research-lint research-format research-typecheck format lint typecheck test test-unit migrate ci precommit

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

frontend-test:
	cd frontend && npm test

frontend-typecheck:
	cd frontend && npm run typecheck

frontend-build:
	cd frontend && npm run build

frontend-audit:
	cd frontend && npm audit --audit-level=high

simulation-test:
	cd simulation-engine && PYTHONPATH=. uv run pytest -q

simulation-lint:
	cd simulation-engine && uv run ruff check app tests smoke && uv run black --check app tests smoke

simulation-format:
	cd simulation-engine && uv run ruff check --fix app tests smoke && uv run black app tests smoke

research-test:
	PYTHONPATH=. uv run --project backend pytest -q research/tests

research-lint:
	uv run --project backend ruff check research && uv run --project backend black --check research

research-format:
	uv run --project backend ruff check --fix research && uv run --project backend black research

research-typecheck:
	MYPYPATH=. uv run --project backend mypy --config-file backend/pyproject.toml research

format: backend-format simulation-format research-format

lint: backend-lint simulation-lint research-lint

typecheck: backend-typecheck frontend-typecheck research-typecheck

test: backend-test frontend-test simulation-test research-test

test-unit: backend-test-unit frontend-test simulation-test research-test

backend-security:
	cd backend && uv run bandit -c pyproject.toml -r app && uv run pip-audit

migrate:
	cd backend && uv run alembic upgrade head

precommit:
	uv run --project backend pre-commit run --all-files

ci: lint backend-typecheck
	./scripts/run-backend-tests.sh coverage
	$(MAKE) frontend-typecheck
	$(MAKE) frontend-test
	$(MAKE) frontend-build
	$(MAKE) frontend-audit
	$(MAKE) simulation-test
	$(MAKE) research-test
	$(MAKE) research-typecheck
	cd backend && uv run bandit -c pyproject.toml -r app && uv run pip-audit
