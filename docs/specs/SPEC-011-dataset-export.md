# SPEC-011 — Dataset Export

**Status:** Draft

**Version:** 1.0

**Document Owner:** Project Team

**Last Updated:** 2026

---

# Depends on

- SPEC-003 — Facilities
- SPEC-004 — Charging Stations
- SPEC-005 — Identity and Access
- SPEC-006 — Reservations
- SPEC-007 — Charging Sessions
- SPEC-008 — Telemetry
- SPEC-010 — Analytics

# Enables

- SPEC-012 — Predictions
- External AI Research Environment

---

# 1. Purpose

This specification defines the Dataset Export capability of the Smart Charging Experimentation Platform (SCEP).

Dataset Export provides a reproducible mechanism for transforming persisted operational and analytical information into research-ready datasets while preserving the integrity of the transactional platform.

The exported datasets enable experimentation, statistical analysis, machine learning workflows and offline evaluation without requiring direct access to the operational database.

This specification defines:

- the Dataset Export module;
- dataset terminology;
- dataset categories;
- export profiles;
- dataset lifecycle;
- export artifact structure;
- metadata and reproducibility requirements;
- supported export formats;
- authorization;
- REST API contracts;
- storage abstraction;
- operational configuration;
- observability;
- acceptance criteria;
- testing requirements.

Version 1 focuses on Smart Charging data while preserving a domain-independent architecture capable of supporting future business domains.

---

# 2. Goals

Dataset Export shall:

- generate reproducible datasets;
- transform operational and analytical information into portable research artifacts;
- support Artificial Intelligence experimentation;
- support offline statistical analysis;
- preserve referential integrity within exported datasets;
- guarantee dataset reproducibility;
- provide metadata describing dataset provenance;
- decouple dataset generation from the HTTP request lifecycle;
- reuse existing authorization rules;
- avoid direct database access from external research environments;
- remain extensible for future dataset types;
- remain independent from specific worker technologies.

---

# 3. Scope

This specification includes:

- dataset generation;
- dataset metadata;
- dataset lifecycle;
- export requests;
- operational datasets;
- analytical datasets;
- export profiles;
- dataset artifacts;
- artifact download;
- reproducibility metadata;
- storage abstraction;
- authorization;
- REST API contracts;
- OpenAPI documentation;
- observability;
- acceptance criteria;
- testing requirements.

## Out of Scope

The following capabilities are intentionally outside the scope of Version 1:

- feature engineering;
- dataset labeling;
- machine learning training;
- experiment tracking;
- Feature Store integration;
- Model Registry integration;
- prediction serving;
- scheduled dataset generation;
- ETL pipelines;
- cloud object storage integrations;
- external Data Lakes;
- dataset version management;
- Domain Event exports;
- Digital Twin execution.

Dataset Export is responsible only for generating datasets from persisted information.

Artificial Intelligence workflows shall execute outside the Backend API, as defined by ADR-008.

---

# 4. Relationship with Existing Domains

Dataset Export does not own business information.

Instead, it materializes information already owned by existing domains into portable research artifacts.

Version 1 may consume information produced by:

- Facilities;
- Charging Stations;
- Connectors;
- Reservations;
- Charging Sessions;
- Telemetry;
- Analytics.

Version 1 does not export Domain Events directly.

Future versions may introduce event-based datasets without changing the public architecture defined by this specification.

Dataset Export shall never:

- create operational entities;
- modify operational entities;
- redefine business rules already implemented by operational domains;
- replace Analytics;
- expose direct database access.

Its responsibility is limited to materializing datasets using information already persisted by the platform.

---

# 5. Architecture

Dataset Export is a cross-cutting platform capability.

It acts as the integration point between the transactional platform and external research environments.

```text
                   REST API
                       │
                       ▼
            Dataset Export Module
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
   Operational    Analytical    Metadata
     Export         Export       Builder
          │            │
          └──────┬─────┘
                 ▼
          Artifact Builder
                 │
                 ▼
      Dataset Artifact Storage
```

Dataset Export shall generate datasets using existing operational persistence and Analytics projections.

The module shall not duplicate business logic already defined elsewhere.

Whenever analytical information is exported, the implementation shall reuse Analytics instead of recalculating metrics.

Dataset generation shall be decoupled from the HTTP request that creates the export.

The implementation may choose any execution mechanism capable of preserving the externally observable lifecycle defined by this specification.

Possible implementations include, but are not limited to:

- background tasks;
- asynchronous coroutines;
- worker threads;
- job queues;
- dedicated worker processes.

This specification intentionally does not mandate any execution technology.

Regardless of the chosen implementation, the observable behavior exposed by the REST API shall remain identical.

The Dataset Export module shall expose only stable REST contracts and shall not leak implementation details regarding scheduling or execution.

---

# 6. Ubiquitous Language

The following terms establish the ubiquitous language for Dataset Export.

| Term | Description |
|------|-------------|
| Dataset | A portable representation of operational or analytical information generated by the platform. |
| Dataset Export | A request to generate a dataset artifact. |
| Dataset Type | The semantic classification of the exported dataset. |
| Dataset Category | High-level grouping of dataset types. |
| Export Profile | Defines how information shall be exposed according to the intended consumer. |
| Dataset Artifact | The generated file delivered to the requester. |
| Manifest | Metadata describing the exported dataset. |
| Data Cutoff | The timestamp representing the snapshot boundary of exported information. |
| Schema Version | Version of the exported dataset structure. |
| Artifact Storage | Component responsible for storing generated artifacts. |

---

# 7. Dataset Categories

Version 1 defines two dataset categories.

## Operational Datasets

Operational datasets contain information directly persisted by business domains.

These datasets represent transactional data and may be consumed for:

- exploratory analysis;
- offline simulations;
- machine learning;
- auditing;
- integration testing.

Operational datasets are generated directly from persisted operational entities.

Examples include:

- Charging Sessions;
- Telemetry.

---

## Analytical Datasets

Analytical datasets contain information already processed by the Analytics module.

These datasets reuse the business semantics already defined by SPEC-010 and shall not duplicate analytical calculations.

Examples include:

- Occupancy metrics;
- Energy summaries;
- Reservation metrics.

Dataset Export shall reuse Analytics projections whenever analytical information is requested.

---

# 8. Supported Dataset Types

Version 1 defines the following dataset types.

| Dataset Type | Category | Source |
|--------------|----------|--------|
| OPERATIONAL_CHARGING_SESSIONS | Operational | Charging Sessions |
| OPERATIONAL_TELEMETRY | Operational | Telemetry |
| ANALYTICAL_OCCUPANCY | Analytical | Analytics |

Future specifications may introduce additional dataset types without changing the public architecture defined by this specification.

Dataset types shall be version-independent.

Changes to exported schemas shall be managed through schema versioning rather than introducing replacement dataset types.

---

# 9. Export Profiles

Export Profiles define how information shall be exposed according to the intended consumer.

Version 1 defines two export profiles.

## ADMINISTRATIVE

Administrative exports are intended for platform operators.

Administrative datasets may contain information required for operational analysis.

The exact set of exported attributes depends on the selected dataset type and authorization rules.

---

## RESEARCH

Research exports are intended for Artificial Intelligence experimentation, statistical analysis and academic research.

Research datasets shall remove or pseudonymize sensitive information whenever applicable.

When pseudonymization is applied, referential integrity within the exported dataset shall be preserved.

This specification intentionally does not prescribe a particular pseudonymization algorithm.

---

# 10. Dataset Export Lifecycle

Dataset generation is represented as a persistent Dataset Export resource.

Each export shall progress through the following lifecycle.

```text
            POST
              │
              ▼
          PENDING
              │
              ▼
        PROCESSING
          │       │
          │       │
          ▼       ▼
    COMPLETED   FAILED
```

## PENDING

The export request has been accepted.

Dataset generation has not yet started.

---

## PROCESSING

Dataset generation is currently executing.

The generated artifact is not yet available for download.

---

## COMPLETED

Dataset generation finished successfully.

The generated artifact is available for download until its retention period expires.

---

## FAILED

Dataset generation could not be completed.

Implementations should provide diagnostic information suitable for operational troubleshooting.

---

# State Transitions

The following transitions are valid.

| Current | Next |
|----------|------|
| PENDING | PROCESSING |
| PROCESSING | COMPLETED |
| PROCESSING | FAILED |

No other transitions are permitted.

Dataset Export resources shall be immutable after reaching either COMPLETED or FAILED.

The retention period of generated artifacts is implementation configurable.

Artifact expiration shall not modify the lifecycle state of the Dataset Export resource.

---

# 11. Dataset Structure

A completed Dataset Export shall produce a single downloadable artifact.

Version 1 defines ZIP as the standard artifact container.

The ZIP archive shall contain:

```text
dataset-export.zip
├── manifest.json
└── data.(csv|parquet)
```

Additional supporting files may be introduced by future specifications without breaking backward compatibility.

The artifact structure shall remain stable for a given schema version.

---

## Data File

The primary data file contains the exported dataset.

Version 1 supports:

- CSV
- Parquet

The requested format shall be specified during export creation.

If a requested format is not enabled by the platform configuration, the request shall be rejected.

---

## Manifest

Every exported dataset shall contain a manifest describing the dataset provenance.

The manifest enables reproducibility, auditing and offline validation.

---

# 12. Manifest Contract

Version 1 defines the following mandatory manifest fields.

| Field | Description |
|------|-------------|
| dataset_id | Unique identifier of the generated dataset. |
| dataset_type | Dataset type. |
| export_profile | Administrative or Research. |
| schema_version | Dataset schema version. |
| generated_at | Dataset generation timestamp (UTC). |
| data_cutoff_at | Snapshot timestamp used during generation. |
| application_version | Backend application version. |
| source_revision | Source code revision used to generate the dataset. |
| format | CSV or PARQUET. |
| filters | Export filters. |
| row_count | Number of exported records. |
| checksum | Artifact checksum. |

Example:

```json
{
  "dataset_id": "0d80cb12-a738-4c4d-a315-2e72c7d3b5e1",
  "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
  "export_profile": "RESEARCH",
  "schema_version": "1.0.0",
  "generated_at": "2026-08-15T18:23:41Z",
  "data_cutoff_at": "2026-08-15T18:23:00Z",
  "application_version": "1.7.0",
  "source_revision": "a82d0a5",
  "format": "PARQUET",
  "filters": {
    "facility_id": "facility-01",
    "from": "2026-08-01T00:00:00Z",
    "to": "2026-08-15T00:00:00Z"
  },
  "row_count": 18425,
  "checksum": "sha256:..."
}
```

---

## Reproducibility

The manifest shall contain sufficient information to allow future consumers to understand how the dataset was produced.

Implementations should guarantee that identical source data and identical filters produce equivalent datasets.

The checksum shall be calculated over the generated artifact.

---

# 13. Export Filters

Each dataset type may define its own supported filters.

Version 1 standardizes the following common filters.

| Filter | Description |
|---------|-------------|
| facility_id | Facility identifier. |
| station_id | Charging station identifier. |
| connector_id | Connector identifier. |
| from | Inclusive lower time boundary. |
| to | Exclusive upper time boundary. |
| timezone | Time zone used for analytical aggregation. |

Analytical datasets may define additional filters specific to their domain.

Unsupported filters shall be rejected.

---

# 14. Storage Model

Dataset Export metadata and generated artifacts have different persistence requirements.

Metadata shall be stored by the transactional persistence layer.

Generated artifacts shall be stored outside the transactional database.

```text
DatasetExport
        │
        ▼
 PostgreSQL
   Metadata
        │
        ▼
 Artifact Storage
        │
        ▼
 ZIP Artifact
```

This separation avoids storing large binary objects inside the transactional database.

The implementation shall expose a storage abstraction responsible for persisting and retrieving generated artifacts.

Example implementations include:

- local filesystem;
- mounted persistent volume;
- object storage.

This specification intentionally does not mandate a storage technology.

---

## Artifact Retention

Generated artifacts shall remain available for a configurable retention period.

After expiration:

- the Dataset Export resource shall remain available;
- metadata shall remain available;
- the artifact may be removed.

Download requests issued after artifact removal shall return an appropriate client error.

---

# 15. Operational Configuration

Dataset Export introduces operational parameters that may vary between deployments.

These parameters are implementation configurable.

Typical configurable values include:

- maximum export window;
- maximum exported rows;
- maximum artifact size;
- maximum concurrent exports;
- artifact retention period;
- enabled export formats;
- artifact storage location.

These parameters affect operational characteristics only.

Business semantics defined by this specification shall not depend on deployment configuration.

---

# 16. REST API

Dataset Export exposes a resource-oriented REST API.

All endpoints require authentication.

Authorization rules are defined in Section 17.

---

## Create Dataset Export

Creates a new dataset export request.

Generation shall begin independently from the HTTP request lifecycle.

### Request

```http
POST /dataset-exports
```

```json
{
  "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
  "export_profile": "RESEARCH",
  "format": "PARQUET",
  "filters": {
    "facility_id": "facility-01",
    "from": "2026-08-01T00:00:00Z",
    "to": "2026-08-15T00:00:00Z"
  }
}
```

### Response

```http
202 Accepted
```

```json
{
  "id": "export-123",
  "status": "PENDING"
}
```

---

## List Dataset Exports

Returns previously requested exports visible to the authenticated user.

### Request

```http
GET /dataset-exports
```

### Response

```json
[
  {
    "id": "export-123",
    "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
    "status": "COMPLETED",
    "created_at": "...",
    "completed_at": "..."
  }
]
```

---

## Retrieve Dataset Export

Returns metadata describing a Dataset Export.

### Request

```http
GET /dataset-exports/{dataset_export_id}
```

### Response

```json
{
  "id": "export-123",
  "status": "COMPLETED",
  "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
  "export_profile": "RESEARCH",
  "format": "PARQUET",
  "created_at": "...",
  "started_at": "...",
  "completed_at": "...",
  "manifest": {
    ...
  }
}
```

---

## Download Dataset Artifact

Downloads the generated artifact.

Downloads shall only be permitted for completed exports whose artifacts are still available.

### Request

```http
GET /dataset-exports/{dataset_export_id}/download
```

### Response

```http
200 OK
Content-Type: application/zip
```

If the artifact no longer exists, the server shall return an appropriate client error.

---

# Error Handling

Typical client errors include:

| Status | Description |
|---------|-------------|
| 400 | Invalid request. |
| 401 | Authentication required. |
| 403 | Authorization failure. |
| 404 | Dataset Export not found. |
| 409 | Export cannot be downloaded in its current state. |
| 410 | Artifact is no longer available. |
| 422 | Unsupported export parameters. |

Implementations may provide additional diagnostic information.

---

# 17. Authorization

Dataset Export shall reuse the platform authorization model.

Version 1 defines the following roles.

| Role | Permissions |
|------|-------------|
| Platform Administrator | Full access. |
| Facility Operator | Export datasets belonging to managed facilities. |
| Researcher | Export datasets permitted for research. |

Authorization shall be evaluated before dataset generation begins.

Users shall never receive data belonging to facilities outside their authorization scope.

Research datasets shall not bypass authorization rules.

---

# 18. Reproducibility

Dataset Export is designed to support reproducible experimentation.

Each exported dataset shall contain sufficient metadata to identify:

- exported dataset type;
- export profile;
- export filters;
- generation timestamp;
- snapshot timestamp;
- application version;
- schema version;
- source revision.

The implementation should produce equivalent datasets whenever:

- the same dataset type is requested;
- identical filters are provided;
- identical source data exists.

Minor differences caused by artifact metadata (for example ZIP timestamps) are implementation dependent.

---

# 19. Operational Limits

Dataset Export may impose implementation-defined operational limits.

Examples include:

- maximum export duration;
- maximum export window;
- maximum exported rows;
- maximum artifact size;
- maximum concurrent exports.

These limits shall be configurable.

Requests exceeding configured limits shall be rejected before dataset generation begins whenever possible.

---

# 20. Observability

Dataset Export shall integrate with the platform observability infrastructure.

Implementations should expose information suitable for monitoring and operational troubleshooting.

Recommended metrics include:

- export requests;
- successful exports;
- failed exports;
- export duration;
- generated artifact size;
- concurrent exports.

Dataset generation failures should generate structured log entries containing:

- dataset identifier;
- dataset type;
- export profile;
- lifecycle state;
- failure reason.

Long-running export operations should be traceable using the platform distributed tracing infrastructure.

---

# 21. OpenAPI Requirements

The OpenAPI specification shall document:

- all Dataset Export endpoints;
- request schemas;
- response schemas;
- lifecycle states;
- dataset types;
- export profiles;
- supported formats;
- validation rules;
- authentication requirements.

Enumerations shall be represented as OpenAPI enums whenever applicable.

Examples shall be provided for every request and response payload.

---

# 22. Acceptance Criteria

An implementation conforms to this specification when all of the following conditions are satisfied.

- Dataset generation is initiated through the REST API.
- Dataset generation is decoupled from the originating HTTP request.
- Dataset Export resources expose the lifecycle defined by this specification.
- Generated artifacts follow the required ZIP structure.
- Every artifact contains a manifest.
- Supported dataset formats are implemented.
- Authorization rules are enforced.
- Operational datasets preserve referential integrity.
- Research datasets preserve referential integrity when pseudonymization is applied.
- Generated artifacts remain reproducible through manifest metadata.
- Download is only possible after successful completion.
- Artifact retention is enforced.
- OpenAPI documentation is complete.

---

# 23. Testing Requirements

Implementations shall include automated tests covering at least:

## Unit Tests

- dataset validation;
- lifecycle transitions;
- manifest generation;
- filter validation;
- authorization rules.

---

## Integration Tests

- export creation;
- export execution;
- artifact persistence;
- artifact retrieval;
- download endpoint;
- storage abstraction.

---

## API Tests

- successful export creation;
- invalid requests;
- authorization failures;
- lifecycle queries;
- artifact download;
- expired artifacts.

---

## Compatibility Tests

Tests shall verify that supported dataset formats produce equivalent datasets for identical source information.

---

# Future Extensions

Potential future enhancements include:

- additional dataset types;
- Domain Event datasets;
- scheduled exports;
- cloud object storage;
- incremental exports;
- dataset partitioning;
- dataset encryption;
- dataset signing;
- Digital Twin datasets;
- AI-ready feature datasets.

These capabilities are intentionally excluded from Version 1 and shall be defined by future specifications.