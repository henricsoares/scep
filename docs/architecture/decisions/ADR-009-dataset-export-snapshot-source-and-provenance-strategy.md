# ADR-009 — Dataset Export Snapshot, Source and Provenance Strategy

**Status:** Accepted
**Date:** 2026
**Related Specs:**

* `SPEC-009-domain-events.md`
* `SPEC-010-analytics.md`
* `SPEC-011-dataset-export.md`
* `ADR-003-event-driven-architecture.md`
* `ADR-008-dataset-export-and-ai-environment.md`

---

# Context

Dataset Export executes asynchronously from the HTTP request that creates an export resource.

The operational persistence model stores current mutable state for entities such as Reservations
and Charging Sessions. It does not provide temporal tables or another mechanism capable of
reopening historical database state from the time at which the HTTP request was accepted.

The existing Domain Event history records important business facts, but Version 1 event payloads
are not complete state snapshots and are not intended to reconstruct every field of an operational
dataset.

Dataset Export therefore requires an explicit decision about:

* when the source boundary is established;
* how a consistent dataset is read;
* which module contracts provide source data;
* which reproducibility properties are guaranteed;
* which provenance fields apply to every export.

This decision qualifies the Dataset Export guidance in ADR-003 and ADR-008 without replacing their
core decisions about event-driven architecture or separation of AI experimentation.

---

# Decision

## Snapshot Boundary

`data_cutoff_at` shall be assigned when dataset generation begins and the database snapshot is
established. It shall not be assigned merely because `POST /dataset-exports` was accepted.

One Dataset Export shall read all operational and analytical inputs from one logically consistent,
read-only PostgreSQL snapshot.

The PostgreSQL implementation shall use `REPEATABLE READ` or an equivalent mechanism that provides
the same observable consistency guarantee.

Time spent in `PENDING` does not preserve source state. Changes committed before processing begins
may appear in the export. Changes committed after the generation snapshot is established shall not
appear.

## Version 1 Sources

Version 1 operational datasets shall read persisted operational entities through module-owned read
contracts.

Version 1 analytical datasets shall reuse read-only Analytics projections. Dataset Export shall
supply `data_cutoff_at` as the Analytics processing timestamp so every analytical bucket uses the
same time boundary.

Domain Events shall not be used to reconstruct Version 1 dataset rows. Event-oriented datasets and
event-history reconstruction remain possible future approaches.

Direct Domain Event datasets remain outside Version 1.

## Dataset Export Event

Dataset Export shall publish `DatasetExportCompleted` after:

1. the data file and manifest have been generated;
2. the artifact has been stored successfully;
3. the Dataset Export resource has transitioned to `COMPLETED`.

The event shall follow the envelope, persistence and dispatch conventions defined by SPEC-009.
After artifact storage succeeds, the `COMPLETED` metadata transition and event persistence shall
occur in the same database transaction, with dispatch after commit.

Version 1 does not require lifecycle events for `PENDING`, `PROCESSING` or `FAILED`.

## Integrity, Provenance and Reproducibility

Version 1 guarantees:

* artifact integrity through recorded checksums;
* provenance through canonical export configuration, schema, cutoff and application metadata;
* deterministic generation when schema, parameters, implementation revision and source snapshot
  are equivalent.

Version 1 does not guarantee:

* reconstruction of historical operational state;
* historical reproducibility after source data or application revisions are unavailable;
* simulation reproducibility.

Simulation reproducibility belongs to the Digital Twin Simulation Engine and its future functional
specification.

## Universal and Conditional Metadata

Experiment identifiers, feature descriptions, simulation seeds and simulation parameters are not
universal Dataset Export metadata.

Feature engineering belongs to the independent AI Research Environment established by ADR-008.
Simulation and experiment metadata shall be included only when another implemented specification
provides truthful and unambiguous source lineage.

Future lineage may be represented through an optional structured `source_lineage` object. This
object is outside Version 1.

## Technology Independence

This decision does not mandate:

* a worker framework;
* a job queue;
* a process topology;
* an artifact-storage provider.

Worker, queue and artifact-storage technologies remain replaceable provided the snapshot,
lifecycle and artifact contracts are preserved.

---

# Rationale

Assigning the cutoff at processing time is the simplest correct design for the current persistence
model. It avoids promising historical reconstruction that the platform cannot provide.

A single consistent database snapshot prevents a long-running export from mixing source states
committed at different times.

Module-owned read contracts preserve the Modular Monolith boundaries established by ADR-001 and
ADR-004 while allowing Dataset Export to materialize cross-cutting research artifacts.

Reusing Analytics projections preserves the metric definitions and timezone behavior established
by SPEC-010 without duplicating analytical formulas.

Separating universal export provenance from conditional simulation or experiment lineage prevents
the manifest from claiming metadata that cannot be derived truthfully for mixed or ordinary
operational data.

---

# Alternatives Considered

## Cutoff at HTTP Acceptance

Rejected because the current persistence model cannot reopen the database state that existed when
the request was accepted.

## Historical Reconstruction from Domain Events

Rejected for Version 1 because existing event payloads are not complete entity snapshots and the
additional reconstruction model is unnecessary for the MVP.

## Materialize Source Rows at HTTP Acceptance

Rejected because it would move substantial generation work into the request path or require an
additional staging model.

## Require Experiment and Simulation Metadata for Every Export

Rejected because ordinary operational exports may not belong to an experiment or a single
simulation run, and feature descriptions are produced by external AI workflows.

---

# Consequences

## Positive Consequences

* snapshot semantics are implementable with current PostgreSQL persistence;
* asynchronous requests remain lightweight;
* Analytics exports remain deterministic within one generation attempt;
* module ownership remains explicit;
* provenance does not overstate unavailable experiment or simulation lineage;
* future event-oriented datasets remain possible.

## Negative Consequences

* source changes committed while an export is `PENDING` may appear in the artifact;
* a database snapshot cannot be resumed after the process and transaction are lost;
* regenerating an old artifact is not guaranteed after source state changes;
* future simulation lineage requires additional domain contracts.

---

# Relationship with Existing Decisions

This decision:

* preserves ADR-001 by requiring module-owned read contracts;
* preserves ADR-003 while making event consumption optional for future Dataset Export versions;
* preserves ADR-004 by using PostgreSQL as the authoritative operational data store;
* preserves ADR-005 by leaving simulation reproducibility with the external Simulation Engine;
* preserves ADR-006 by requiring traceable background generation;
* preserves ADR-008 by keeping AI experimentation external and using datasets and REST APIs as the
  integration boundary.

---

# Decision Outcome

Dataset Export Version 1 will generate artifacts from one processing-time, read-only source
snapshot using operational read contracts and Analytics projections.

It will provide integrity, provenance and deterministic generation without claiming historical or
simulation reproducibility that the current platform cannot support.
