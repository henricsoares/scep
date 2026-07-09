# Contributing to SCEP

SCEP is a single-developer academic/research project, so the contribution process should stay lightweight while preserving traceability from architecture decisions to implementation.

## Specification-Driven Development

SCEP uses Specification-Driven Development. Business and platform capabilities should be implemented only after the relevant specification is approved under `docs/specs/`.

A typical change should follow this flow:

```text
Architecture / ADRs → Specification → Issue → Branch → Pull Request → Validation → Merge
```

Small maintenance changes may skip a dedicated specification when they do not change product behavior or architecture, but the PR should say why.

## Architecture, ADRs, Specs, Issues and PRs

- **Architecture documents** in `docs/architecture/` describe the system structure and quality goals.
- **ADRs** in `docs/architecture/decisions/` capture decisions that affect architecture, technology choices, boundaries, or long-term trade-offs.
- **Specifications** in `docs/specs/` define what should be implemented for a capability or foundation increment.
- **Issues** track implementation work for one approved specification, bug, or technical debt item.
- **Pull Requests** should connect the code change back to the relevant specification, ADR, or issue.

## GitHub Flow

Use GitHub Flow:

1. Create a branch from `main`.
2. Keep the branch focused on one specification, bug, or maintenance task.
3. Open a Pull Request into `main`.
4. Run and document relevant validation.
5. Merge after the PR is complete and checks pass.

## Branch Naming

Use short, descriptive branch names:

- `feature/spec-001-project-foundation`
- `feature/spec-003-facilities`
- `fix/health-readiness-check`
- `chore/repository-governance`
- `docs/update-architecture-links`

## Conventional Commits

Use Conventional Commits for commit messages:

- `feat: add health endpoints`
- `fix: correct readiness check`
- `test: add health endpoint tests`
- `docs: update contributing guide`
- `chore: add issue templates`

## Pull Request Expectations

A PR should include:

- a concise summary;
- the related specification, ADR, or maintenance reason;
- architectural impact, if any;
- what is in scope and out of scope;
- validation performed, including commands and results;
- breaking changes or deviations from the specification.

Avoid mixing unrelated business features, refactors, and infrastructure changes in one PR.

## Definition of Done

A change is done when:

- it stays within the approved scope;
- relevant tests and checks pass or limitations are clearly documented;
- documentation is updated when behavior, process, or architecture changes;
- no unrelated features are introduced;
- deviations from the specification are explicitly explained;
- the PR is traceable to a specification, ADR, issue, or maintenance need.

## When to Create a New ADR

Create a new ADR when a change introduces or modifies:

- architectural style or system boundaries;
- technology choices with long-term impact;
- data ownership or persistence strategy;
- integration patterns between containers or modules;
- security, observability, deployment, or quality-attribute trade-offs;
- a meaningful deviation from an existing architecture decision.

Do not create an ADR for routine implementation details, small bug fixes, or documentation-only changes unless they change architectural direction.
