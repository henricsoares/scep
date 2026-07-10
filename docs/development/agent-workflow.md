# AI Agent Development Workflow

## Purpose

This document defines the expected workflow for AI-assisted development within the Smart Charging Experimentation Platform (SCEP).

Its purpose is to ensure that every implementation follows the same engineering standards regardless of the AI tool being used.

Examples include, but are not limited to:

* OpenAI Codex
* GitHub Copilot
* Claude Code
* Cursor
* Gemini CLI
* Future AI-assisted development tools

The workflow is tool-agnostic.

---

# Development Philosophy

SCEP follows a **Specification-Driven Development** approach.

Code is not the starting point.

Every implementation begins with approved documentation.

The expected sequence is:

```text
Architecture

↓

Architecture Decision Records (ADRs)

↓

Functional Specification

↓

Implementation

↓

Automated Validation

↓

Smoke Test

↓

Code Review

↓

Merge

↓

Release
```

An implementation must never introduce architectural decisions that contradict approved ADRs or Specifications.

---

# General Principles

An AI agent should:

* implement only the requested scope;
* avoid unnecessary refactoring;
* avoid speculative features;
* preserve architectural consistency;
* document ambiguities instead of making assumptions;
* prefer small and focused Pull Requests.

When documentation and prompts disagree, approved project documentation takes precedence.

---

# Repository Workflow

Every implementation should begin from the latest `main` branch.

Recommended workflow:

```text
Issue

↓

Create branch

↓

Implementation

↓

Pre-commit

↓

Quality Gates

↓

Smoke Test

↓

Pull Request

↓

Review

↓

Merge (Squash)

↓

Tag (when applicable)
```

---

# Branch Naming

Use descriptive branch names.

Examples:

```text
feat/spec-005-identity-access

fix/openapi-validation

debt/automatic-alembic-migrations

docs/project-retrospective-v1
```

---

# Commit Convention

Follow Conventional Commits.

Examples:

```text
feat: implement charging station aggregate

fix: preserve updated_at during station update

docs: add development retrospective

debt: automate Alembic migrations
```

---

# Scope Control

Implement only what belongs to the approved Specification or Issue.

Do not introduce:

* unrelated refactoring;
* additional features;
* architectural redesign;
* experimental frameworks.

If an ambiguity exists:

* document it;
* request clarification;
* avoid speculative implementation.

---

# Required Validation

Before opening a Pull Request, execute:

```bash
uv run --project backend pre-commit run --all-files
```

Then execute all project quality gates.

Typical validation includes:

* Ruff
* Black
* MyPy
* Pytest
* Coverage
* Bandit
* pip-audit

If a validation cannot be executed because of environment limitations, document the reason explicitly.

---

# Smoke Test

Whenever application behavior changes, execute a Docker Compose smoke test.

The smoke test should verify:

* container startup;
* automatic database migrations;
* backend health;
* OpenAPI;
* implemented REST endpoints;
* observability stack;
* integration between services.

Smoke tests complement automated testing and are required before functional Pull Requests.

---

# Pull Requests

Every Pull Request should:

* use the repository template;
* reference the related Issue when applicable;
* describe implemented scope;
* list validation commands;
* report smoke-test results;
* document known limitations;
* state deferred work when applicable.

Pull Requests should remain focused on a single objective.

---

# Documentation

Architecture documents, ADRs and Specifications are authoritative.

Do not modify them unless explicitly requested.

Documentation updates should accompany implementation whenever project behavior or developer workflow changes.

---

# Security

Never commit:

* `.env`
* credentials
* API keys
* secrets
* generated cache files
* virtual environments

Always review the Git diff before committing.

---

# Definition of Done

A task is considered complete when:

* implementation satisfies the approved Specification or Issue;
* architecture remains consistent;
* quality gates pass;
* smoke test succeeds;
* documentation is updated when necessary;
* Pull Request is ready for review.

---

# Guiding Principle

The objective of AI-assisted development is not to maximize code generation.

The objective is to produce maintainable, reviewable and architecturally consistent software through a repeatable engineering process.
