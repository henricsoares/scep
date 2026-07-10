# Contributing

SCEP is a single-developer academic and research project. Contributions should keep the repository easy to understand, reproducible and traceable to the documented Specification-Driven Development process.

## Specification-Driven Development

Functional work should start from an approved specification in `docs/specs/`. Specifications define what the platform must do and serve as the implementation contract for each development iteration.

The expected flow is:

```text
Architecture -> ADRs -> Functional Specifications -> Issues -> Pull Requests
```

Architecture documents in `docs/architecture/` establish the technical baseline. Architecture Decision Records (ADRs) document important technical decisions. Functional specifications describe business capabilities. Issues break one approved specification into implementable work. Pull requests deliver and validate those changes.

## GitHub Flow

Use short-lived branches from `main` and open a pull request back into `main`.

Keep each pull request focused on one specification, bug fix, documentation update or technical-debt item. Avoid mixing unrelated application, infrastructure and documentation changes.

## Branch Naming

Use descriptive lowercase branch names:

- `feat/spec-005-identity-access`
- `fix/health-readiness-check`
- `docs/spec-004-clarification`
- `chore/repository-governance`
- `debt/backend-test-helpers`

## Conventional Commits

Use Conventional Commit prefixes where practical:

- `feat:` for new behavior
- `fix:` for bug fixes
- `docs:` for documentation
- `test:` for tests
- `refactor:` for behavior-preserving code changes
- `chore:` for repository maintenance

## Labels

Use the official label taxonomy to describe the type of change, affected area and planning context.

Type labels:

- `feature`
- `bug`
- `documentation`
- `technical-debt`
- `architecture`
- `repository`

Area labels:

- `backend`
- `frontend`
- `simulation`
- `observability`
- `database`
- `devops`

Planning labels:

- `spec`
- `adr`
- `research`
- `enhancement`

## Pull Request Expectations

Each pull request should explain:

- what changed;
- which specification, ADR or issue it relates to;
- whether there is architectural impact;
- how it was validated;
- what is intentionally out of scope.

For implementation work, link the approved specification and keep terminology consistent with `SPEC-002 — Domain Model and Ubiquitous Language`.

## Definition of Done

A change is done when:

- the scope matches the linked specification, issue or documented rationale;
- relevant tests, checks or manual validation were performed;
- documentation is updated when behavior, process or architecture changes;
- architectural impact was considered;
- no unrelated files were changed;
- follow-up work is captured in notes or issues when needed.

## When to Create a New ADR

Create a new ADR before implementation when a change introduces or revises an architectural decision, such as:

- changing the system structure or module boundaries;
- adopting or replacing a major technology;
- changing persistence, eventing, observability, security or deployment strategy;
- introducing a cross-cutting quality trade-off.

Do not create an ADR for routine implementation details, small refactors or decisions already covered by the architecture baseline.

## AI-assisted Development

When using an AI development agent, follow the workflow defined in:

`docs/development/agent-workflow.md`