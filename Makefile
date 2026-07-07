.PHONY: up down logs backend-test backend-lint backend-format backend-typecheck backend-security migrate ci precommit
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

backend-security:
	cd backend && uv run bandit -c pyproject.toml -r app && uv run pip-audit

migrate:
	cd backend && uv run alembic upgrade head

precommit:
	cd backend && uv run pre-commit run --all-files

ci: backend-lint backend-typecheck backend-test backend-security
	cd backend && uv run coverage run -m pytest && uv run coverage report
