# ADR-007 — Adopt DevSecOps and Continuous Integration as the Development Strategy

**Status:** Accepted
**Date:** 2026
**Related Specs:**

* `006-quality-attributes.md`
* `007-observability-view.md`
* `008-deployment-runtime-view.md`

---

# Context

The Smart Charging Experimentation Platform (SCEP) is intended to demonstrate not only software functionality, but also modern Software Engineering practices.

The project serves as both:

* a research platform;
* a software engineering case study.

Therefore, software quality cannot depend exclusively on manual verification.

The development process must guarantee that every modification is continuously validated with respect to:

* functionality;
* architecture;
* coding standards;
* security;
* documentation.

This aligns with the objectives of the postgraduate program, particularly the disciplines related to Software Quality, Configuration Management and Modern Software Engineering.

---

# Decision

SCEP will adopt a **DevSecOps-oriented development process** supported by an automated **Continuous Integration (CI)** pipeline.

Every code change shall be validated automatically before being integrated into the main branch.

Security verification is treated as an integral part of software quality rather than a separate activity.

---

# Rationale

The primary goal of this decision is to ensure that software quality is evaluated continuously throughout the project lifecycle.

Rather than detecting problems near project completion, quality controls are executed immediately after every proposed change.

This approach improves:

* software reliability;
* maintainability;
* architectural consistency;
* reproducibility;
* development confidence.

It also reflects industry practices commonly adopted in cloud-native and research-oriented software projects.

---

# Alternatives Considered

## Manual Validation

Developers manually execute tests before committing changes.

Advantages:

* minimal infrastructure;
* simple workflow.

Rejected because it is error-prone, non-reproducible and incompatible with continuous software evolution.

---

## Continuous Integration Only

Automate build and testing without security validation.

Advantages:

* faster pipeline;
* simpler implementation.

Rejected because security is considered part of software quality.

---

## DevSecOps Pipeline

Integrate quality, testing and security into the same automated workflow.

Advantages:

* continuous quality verification;
* continuous security verification;
* reproducible builds;
* standardized development process.

Selected.

---

# Consequences

## Positive Consequences

* improved software quality;
* earlier defect detection;
* automated architectural validation;
* reproducible builds;
* standardized code style;
* continuous security assessment;
* simplified onboarding.

---

## Negative Consequences

* additional pipeline execution time;
* greater initial configuration effort;
* stricter development workflow.

These costs are considered acceptable given the project's educational and research objectives.

---

# Development Workflow

Every proposed change follows the same lifecycle.

```text
Developer

      │

      ▼

Feature Branch

      │

      ▼

Pull Request

      │

      ▼

Continuous Integration

      │

      ▼

Code Review

      │

      ▼

Merge

      │

      ▼

Main Branch
```

Direct commits to the main branch are discouraged.

---

# Continuous Integration Pipeline

The minimum CI pipeline shall execute the following stages.

```text
Checkout

↓

Environment Setup

↓

Dependency Installation

↓

Formatting

↓

Linting

↓

Static Type Checking

↓

Unit Tests

↓

Integration Tests

↓

Coverage Validation

↓

Security Scan

↓

Dependency Audit

↓

Docker Build

↓

Documentation Validation
```

The pipeline must fail immediately whenever a mandatory validation step fails.

---

# Development Toolchain

The following tools compose the reference quality pipeline.

## Code Formatting

* Black

---

## Linting

* Ruff

---

## Static Type Checking

* MyPy

---

## Testing

* pytest
* pytest-asyncio

---

## Coverage

* Coverage.py

---

## Security

* Bandit
* pip-audit

---

## Container Validation

* Docker Build

---

## Documentation

* MkDocs
* Mermaid rendering validation (future enhancement)

---

# Security Strategy

Security verification shall occur continuously.

Automated validation includes:

* dependency vulnerability scanning;
* insecure code pattern detection;
* secret leakage prevention (future enhancement);
* input validation through Pydantic;
* authentication verification.

Security shall be incorporated into development rather than postponed until deployment.

---

# Branch Strategy

The project follows a simplified Git workflow.

Recommended branches include:

* `main`
* `develop` (optional)
* `feature/*`
* `fix/*`
* `docs/*`

Each Pull Request should address a single logical change whenever practical.

---

# Code Review

Every Pull Request should be reviewed before merging.

Review should verify:

* architectural consistency;
* specification compliance;
* readability;
* naming conventions;
* testing coverage;
* documentation updates.

Whenever architecture is affected, reviewers should verify consistency with:

* Architecture Specifications;
* ADRs;
* Functional Specifications.

---

# Definition of Done

A feature is considered complete only when all of the following conditions are satisfied.

* implementation completed;
* automated tests passing;
* CI pipeline passing;
* documentation updated;
* architectural rules respected;
* security checks passing;
* code reviewed.

Implementation alone is insufficient.

---

# Quality Gates

A Pull Request should not be merged unless:

* formatting passes;
* linting passes;
* type checking passes;
* unit tests pass;
* integration tests pass;
* coverage target is maintained;
* security scan passes;
* dependency audit passes;
* Docker image builds successfully.

These quality gates establish a consistent engineering baseline.

---

# Relationship with Architecture

The CI pipeline enforces the architectural decisions documented in the project.

Examples include:

* preserving Modular Monolith boundaries;
* validating API contracts;
* ensuring reproducible builds;
* protecting architectural quality.

The pipeline is therefore considered an architectural component rather than merely a development convenience.

---

# Quality Attributes Supported

This decision primarily supports:

| Quality Attribute | Support                             |
| ----------------- | ----------------------------------- |
| Testability       | Continuous automated verification   |
| Maintainability   | Standardized development practices  |
| Reliability       | Early defect detection              |
| Security          | Continuous vulnerability assessment |
| Reproducibility   | Deterministic builds and validation |
| Modularity        | Architectural consistency checks    |

---

# Risks and Mitigations

## Risk: Slow Pipeline

A growing test suite may increase execution time.

Mitigation:

* parallel execution where appropriate;
* fast unit tests;
* optimize integration tests;
* separate optional validations if necessary.

---

## Risk: Excessively Strict Rules

Developers may perceive the workflow as restrictive.

Mitigation:

* automate repetitive tasks;
* provide clear error messages;
* maintain well-documented contribution guidelines.

---

## Risk: False Sense of Security

Passing automated checks does not guarantee software correctness.

Mitigation:

* code reviews;
* architectural reviews;
* exploratory testing;
* research validation.

---

# Future Evolution

Future improvements may include:

* automated dependency updates;
* Software Bill of Materials (SBOM) generation;
* container image signing;
* secret scanning;
* Infrastructure as Code validation;
* GitHub Actions reusable workflows;
* automatic release generation.

These capabilities extend the DevSecOps process without changing its fundamental principles.

---

# Decision Outcome

SCEP adopts a DevSecOps-oriented development strategy supported by Continuous Integration.

Software quality, architectural consistency and security shall be continuously verified through automated pipelines, ensuring that every code change contributes to a reliable, maintainable and reproducible research platform.

This decision reinforces the project's commitment to modern Software Engineering practices and provides a disciplined foundation for the implementation phase.
