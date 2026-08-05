# Study Scope — SCEP Spec-Driven Development Case Study

This document freezes the Pull Request population and classification rules used by the Spec-Driven Development case study before quantitative metrics are calculated.

## Primary quantitative sample

The primary sample contains merged Pull Requests that implemented an executable SCEP capability or a functional/architectural increment required to deliver the MVP.

| PR | Increment | Context | Classification |
| --- | --- | --- | --- |
| #1 | Project foundation | SPEC-001 | PRIMARY |
| #4 | Facilities | SPEC-003 | PRIMARY |
| #9 | Charging Stations and Connectors | SPEC-004 | PRIMARY |
| #17 | Identity and Access | SPEC-005 | PRIMARY |
| #19 | Observability pipelines | SPEC-001 / architectural debt | PRIMARY |
| #23 | Reservations | SPEC-006 | PRIMARY |
| #26 | Charging Sessions | SPEC-007 | PRIMARY |
| #30 | Telemetry | SPEC-008 | PRIMARY |
| #36 | Domain Events | SPEC-009 | PRIMARY |
| #41 | Analytics | SPEC-010 | PRIMARY |
| #45 | Dataset Export | SPEC-011 | PRIMARY |
| #53 | Digital Twin Simulation Engine | SPEC-013 | PRIMARY |
| #55 | Research and non-human authorization | SPEC-012 prerequisite / authorization debt | PRIMARY |
| #56 | Weekly Occupancy Predictions and external research reproducibility | SPEC-012 | PRIMARY |
| #58 | Minimal Web Dashboard | MVP demonstration frontend | PRIMARY |

Primary sample size: **15 Pull Requests**.

## Secondary population

The collector must retain all repository Pull Requests even when they are not part of the primary quantitative sample. Secondary records provide evidence about specification preparation, technical debt, testing work and unsuccessful AI implementation attempts.

### Superseded or unaccepted AI implementation attempts

| PR | Context | Classification | Relationship |
| --- | --- | --- | --- |
| #8 | SPEC-004 implementation attempt | SECONDARY / SUPERSEDED | superseded by #9 |
| #16 | SPEC-005 implementation attempt | SECONDARY / SUPERSEDED | superseded by #17 |
| #40 | SPEC-010 implementation attempt | SECONDARY / SUPERSEDED | superseded by #41 |
| #2 | foundation implementation attempt | SECONDARY / SUPERSEDED | not merged; repository foundation ultimately represented by #1 |

These records are not counted as independently delivered increments, but they are relevant to the analysis of first-attempt acceptance and human supervision.

### Specification and architecture documentation

The following documentation Pull Requests are retained as secondary evidence of the specification phase rather than counted as implementation increments:

- #14 — SPEC-005;
- #21 — SPEC-006;
- #24 — SPEC-007;
- #28 — SPEC-008;
- #34 — SPEC-009;
- #38 — SPEC-010;
- #43 — SPEC-011 architecture alignment;
- #48 — SPEC-012;
- #50 — SPEC-013.

These may support a secondary analysis of specification preparation time, but they are excluded from primary implementation cycle-time statistics.

### Other excluded-from-primary categories

The following kinds of Pull Requests remain available in the raw dataset but are excluded from the primary analysis:

- repository governance and retrospective documentation;
- local development and environment corrections;
- test-only stabilization work;
- release/status documentation;
- housekeeping or administrative changes.

Known examples include #3, #6, #10, #12, #32, #51 and #59.

## Classification fields

Every collected Pull Request receives the following study-level fields, which are kept separate from raw GitHub metadata:

```text
analysis_scope
attempt_status
supersedes_pr
superseded_by_pr
```

Allowed values:

### `analysis_scope`

- `PRIMARY` — included in the main quantitative analysis;
- `SECONDARY` — retained for contextual or exploratory analysis;
- `EXCLUDED` — collected for completeness but not analyzed unless explicitly needed.

### `attempt_status`

- `ACCEPTED` — merged implementation representing the delivered increment;
- `SUPERSEDED` — implementation attempt replaced by another Pull Request;
- `ABANDONED` — implementation attempt closed without replacement established by the study;
- `NOT_APPLICABLE` — documentation, process, test-only or other non-implementation Pull Request.

## Interpretation rule

A merged Pull Request is not automatically considered an independent functional increment, and an unmerged Pull Request is not automatically discarded as irrelevant evidence.

The primary quantitative unit remains the accepted functional Pull Request. Superseded AI attempts are analyzed separately so that the study does not hide failed or rejected first implementations while also avoiding double-counting one functional capability as multiple delivered increments.

## Freeze rule

This scope was defined before calculating the final study metrics. Any later change to the primary sample must be documented with a methodological justification rather than being made because of the numerical result it produces.
