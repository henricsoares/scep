# SPEC-011 — Dataset Export

## Smart Charging Experimentation Platform (SCEP)

**Status:** Draft

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

**Depends on:**

- SPEC-003 — Facilities
- SPEC-004 — Charging Stations
- SPEC-005 — Identity and Access
- SPEC-006 — Reservations
- SPEC-007 — Charging Sessions
- SPEC-008 — Telemetry
- SPEC-010 — Analytics
- ADR-008 — Separate AI Experimentation from the Transactional Platform

**Enables:**

- SPEC-012 — Predictions
- External AI Research Environment

---

# 1. Purpose

This specification defines the Dataset Export capability of the Smart Charging Experimentation Platform (SCEP).

Dataset Export transforms persisted operational data and Analytics projections into portable, research-ready artifacts without exposing direct access to the transactional PostgreSQL database.

The capability provides the controlled integration boundary between the Backend API and the independent AI Research Environment established by ADR-008.

This specification defines:

- Dataset Export terminology and domain concepts;
- operational and analytical dataset categories;
- supported dataset types and schemas;
- Administrative and Research export profiles;
- persistent export lifecycle;
- snapshot and reproducibility rules;
- artifact and manifest contracts;
- CSV and Parquet serialization;
- storage and retention;
- operational configuration;
- REST API contracts;
- authorization;
- observability;
- acceptance criteria;
- testing requirements.

Version 1 focuses on Smart Charging data while preserving an extensible architecture for future dataset types.

---

# 2. Goals

This specification shall:

- provide controlled export of operational and analytical data;
- support offline statistical analysis and Artificial Intelligence experimentation;
- preserve the Backend API as the authoritative owner of operational data;
- prevent direct database access from external AI workflows;
- generate versioned and self-describing datasets;
- preserve referential integrity inside each exported artifact;
- distinguish Administrative exports from Research exports;
- provide deterministic row selection and ordering;
- record sufficient provenance for reproducibility and auditing;
- decouple dataset generation from the originating HTTP request;
- reuse existing domain and Analytics semantics;
- reuse the Identity and Access model defined by SPEC-005;
- keep execution and storage technologies replaceable;
- avoid introducing model training, feature engineering or experiment execution into the Backend API.

---

# 3. Scope

This specification includes:

- persistent Dataset Export resources;
- asynchronous dataset materialization;
- operational datasets;
- analytical datasets;
- Administrative and Research profiles;
- dataset-specific field projections;
- deterministic Research pseudonymization;
- dataset schema versioning;
- data snapshot boundaries;
- ZIP artifacts;
- CSV and Parquet data files;
- `manifest.json`;
- artifact checksums;
- storage abstraction;
- artifact retention;
- export filters;
- operational limits;
- REST API contracts;
- authorization;
- OpenAPI documentation;
- observability;
- automated testing.

## Out of Scope

The following capabilities are intentionally outside Version 1:

- feature engineering;
- dataset labeling;
- model training;
- model validation;
- hyperparameter optimization;
- experiment tracking;
- Feature Store integration;
- Model Registry integration;
- prediction generation or serving;
- scheduled exports;
- recurring exports;
- incremental or append-only exports;
- multi-file partitioned datasets;
- direct Domain Event exports;
- external Data Lake integration;
- cloud object storage requirements;
- dataset encryption or digital signing;
- user-defined SQL;
- arbitrary column selection;
- custom pseudonymization algorithms;
- direct access from the AI Research Environment to PostgreSQL;
- Digital Twin execution.

Feature engineering, model training and experimentation shall remain inside the independent AI Research Environment defined by ADR-008.

---

# 4. Architectural Context

Dataset Export is a cross-cutting platform capability.

It materializes information owned by existing operational domains and Analytics without becoming the owner of that information.

```text
Operational Domains                 Analytics
        │                               │
        └──────────────┬────────────────┘
                       ▼
             Dataset Export Module
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
      Export Metadata      Artifact Builder
         PostgreSQL               │
                                  ▼
                       Dataset Artifact Storage
                                  │
                                  ▼
                         AI Research Environment
```

The Backend API shall remain responsible for:

- selecting authorized source data;
- applying export profile rules;
- generating dataset artifacts;
- persisting export metadata;
- exposing controlled download endpoints.

The AI Research Environment shall:

- consume exported artifacts;
- avoid direct access to operational persistence;
- perform feature engineering and model-related activities independently.

Dataset Export shall never:

- create or modify Facilities, Stations, Connectors, Reservations, Charging Sessions or Telemetry Samples;
- modify Analytics semantics;
- expose arbitrary database access;
- copy AI dependencies into the Backend API;
- train machine learning models.

---

# 5. Design Principles

## 5.1 Contract over Implementation

This specification defines externally observable behavior and required invariants.

It does not mandate:

- a background-task library;
- a job queue;
- a worker framework;
- a process topology;
- a filesystem or object-storage provider.

The implementation may use background tasks, coroutines, threads, queues or dedicated workers, provided the lifecycle and API contracts defined here are preserved.

## 5.2 Reuse Existing Semantics

Operational datasets shall project persisted domain entities.

Analytical datasets shall reuse metric definitions and time-bucket behavior from SPEC-010.

Dataset Export shall not independently redefine:

- Reservation state interpretation;
- Charging Session state interpretation;
- Telemetry meaning;
- occupancy formulas;
- Facility operating-hour semantics;
- timezone aggregation rules.

## 5.3 Reproducibility by Default

Every artifact shall identify:

- what was requested;
- which schema was used;
- which source boundary was applied;
- which application revision generated it;
- how many records were produced;
- how the data file can be integrity-checked.

## 5.4 Explicit Privacy Profile

The requester shall select an Export Profile.

Privacy behavior shall not depend on an undocumented deployment default.

## 5.5 Operational Configuration without Domain Drift

Deployment configuration may control limits, retention, enabled formats and storage locations.

Configuration shall not change dataset field meaning, profile semantics, metric definitions or schema contracts.

---

# 6. Ubiquitous Language

## Dataset Export

A persistent resource representing one request to materialize a dataset.

## Dataset

The logical collection of records produced by a completed Dataset Export.

## Dataset Type

A stable semantic identifier describing the exported information.

Version 1 dataset types are:

```text
OPERATIONAL_CHARGING_SESSIONS
OPERATIONAL_TELEMETRY
ANALYTICAL_OCCUPANCY
```

## Dataset Category

One of:

```text
OPERATIONAL
ANALYTICAL
```

## Export Profile

The privacy and audience policy applied to a dataset.

Version 1 profiles are:

```text
ADMINISTRATIVE
RESEARCH
```

## Dataset Artifact

The downloadable ZIP file produced by a completed export.

## Data File

The CSV or Parquet file inside the artifact.

## Manifest

The `manifest.json` file containing schema, provenance, filter and integrity metadata.

## Schema Version

The version of the data-file contract for one Dataset Type and Export Profile.

## Data Cutoff

The UTC timestamp that bounds the source state considered by generation.

## Export Window

The half-open interval `[from, to)` requested for source record selection or analytical aggregation.

## Artifact Retention

The configurable period during which a completed artifact remains available for download.

## Pseudonymous Identifier

A deterministic, non-original identifier generated for a sensitive source identifier inside one exported dataset.

## Artifact Storage

The abstraction responsible for storing, retrieving and deleting generated artifacts.

---

# 7. Dataset Categories

## 7.1 Operational Datasets

Operational datasets project persisted business records.

They preserve the semantics of their source aggregates and are suitable for:

- exploratory analysis;
- auditing;
- offline processing;
- machine learning preparation;
- integration validation.

Version 1 operational datasets are:

- `OPERATIONAL_CHARGING_SESSIONS`;
- `OPERATIONAL_TELEMETRY`.

## 7.2 Analytical Datasets

Analytical datasets materialize projections defined by SPEC-010.

They are suitable for:

- historical KPI analysis;
- capacity studies;
- occupancy modeling;
- prediction dataset preparation.

Version 1 analytical dataset:

- `ANALYTICAL_OCCUPANCY`.

Analytical exports shall use the same:

- Analysis Window convention;
- Facility operating hours;
- timezone rules;
- granularities;
- metric formulas;
- numeric precision policy

defined by SPEC-010.

---

# 8. Export Profiles

## 8.1 ADMINISTRATIVE

The `ADMINISTRATIVE` profile is intended for authorized platform operation and auditing.

Administrative exports may preserve original platform identifiers required for operational correlation.

Administrative exports shall not include:

- user email;
- display name;
- password data;
- credentials;
- JWT contents;
- secrets;
- authentication metadata not explicitly part of the dataset schema.

## 8.2 RESEARCH

The `RESEARCH` profile is intended for Researchers and Data Scientists.

Research exports shall:

- exclude direct personal identifiers;
- replace sensitive actor, vehicle and producer identifiers with pseudonymous identifiers when those fields are required;
- preserve referential integrity inside the generated artifact;
- avoid exposing the pseudonymization secret or lookup map.

## 8.3 Pseudonymization Scope

Pseudonymization shall be deterministic within one Dataset Export.

The same source identifier appearing multiple times inside the same artifact shall produce the same pseudonymous value.

Different identifier namespaces shall remain distinct.

For example:

```text
owner:123  != vehicle:123
```

The implementation shall derive pseudonymous identifiers from at least:

- Dataset Export identifier or export-specific secret context;
- identifier namespace;
- original identifier;
- a server-controlled secret.

A suitable conceptual construction is:

```text
pseudonym = HMAC(secret, export_id + namespace + original_identifier)
```

This formula is illustrative and does not mandate a cryptographic library or encoding.

Because the export identifier participates in the context, two separate exports may assign different pseudonyms to the same original entity.

## 8.4 Referential Integrity across Dataset Types

Version 1 produces one Dataset Type per Dataset Export.

Therefore, referential integrity is guaranteed within each artifact, not across independently generated exports.

The `OPERATIONAL_TELEMETRY` schema includes Charging Session context so telemetry records can be analyzed and joined by `session_id` inside the same artifact.

A future multi-dataset bundle may define shared pseudonymization across multiple files.

---

# 9. Dataset Type and Schema Versioning

Dataset Type identifiers shall remain stable.

Schema evolution shall use semantic versioning:

```text
MAJOR.MINOR.PATCH
```

- `MAJOR`: incompatible field removal, rename, type change or semantic change;
- `MINOR`: backward-compatible field addition;
- `PATCH`: documentation or serialization correction without changing the logical schema.

Each Dataset Type and Export Profile combination shall declare a schema version.

Version 1 schema versions are:

| Dataset Type | Profile | Schema Version |
|---|---|---|
| `OPERATIONAL_CHARGING_SESSIONS` | `ADMINISTRATIVE` | `1.0.0` |
| `OPERATIONAL_CHARGING_SESSIONS` | `RESEARCH` | `1.0.0` |
| `OPERATIONAL_TELEMETRY` | `ADMINISTRATIVE` | `1.0.0` |
| `OPERATIONAL_TELEMETRY` | `RESEARCH` | `1.0.0` |
| `ANALYTICAL_OCCUPANCY` | `ADMINISTRATIVE` | `1.0.0` |
| `ANALYTICAL_OCCUPANCY` | `RESEARCH` | `1.0.0` |

A schema version shall define:

- ordered column names;
- logical data types;
- nullability;
- units;
- profile-specific transformations;
- deterministic row ordering.

---

# 10. Common Serialization Rules

## 10.1 Timestamp Representation

All persisted operational timestamps shall be exported in UTC.

CSV timestamps shall use RFC 3339 with a `Z` suffix.

Example:

```text
2026-08-15T18:23:41Z
```

Parquet timestamps shall preserve UTC semantics.

Analytical bucket boundaries shall include the requested timezone offset, as defined by SPEC-010.

## 10.2 Null Values

CSV shall represent null values as empty fields.

The literal strings `null`, `None` or `N/A` shall not be used as null markers.

Parquet shall use native null values.

## 10.3 Decimal Values

Power and energy values shall use decimal-compatible serialization without locale-specific separators.

CSV shall use `.` as the decimal separator.

## 10.4 Enumeration Values

Enumerations shall use the canonical values defined by the owning specification.

## 10.5 Boolean Values

CSV boolean values shall use lowercase:

```text
true
false
```

## 10.6 Row Ordering

Every dataset shall define deterministic ordering.

Equivalent source state and request parameters shall produce the same logical row order.

The implementation shall not rely on implicit database ordering.

## 10.7 CSV

CSV files shall:

- use UTF-8;
- include one header row;
- use comma separators;
- use RFC 4180-compatible escaping;
- use `\n` line endings;
- use the schema-defined column order.

## 10.8 Parquet

Parquet files shall:

- preserve the same logical columns and ordering as CSV;
- use logical timestamp and decimal types when supported;
- represent nullability consistently with the schema;
- contain one logical table.

CSV and Parquet outputs for the same Dataset Export request shall be logically equivalent, subject to format-specific physical representation.

---

# 11. Dataset Schemas

## 11.1 `OPERATIONAL_CHARGING_SESSIONS`

### 11.1.1 Selection Rules

A Charging Session shall be selected when:

```text
started_at >= from
AND
started_at < to
```

The export shall additionally apply:

- authorized Facility scope;
- optional Facility filter;
- optional Station filter;
- optional Connector filter;
- `data_cutoff_at`.

Records created or updated after `data_cutoff_at` shall not alter the exported snapshot.

### 11.1.2 Administrative Schema

| Column | Type | Nullable | Description |
|---|---|---:|---|
| `session_id` | UUID/string | No | Original Charging Session identifier. |
| `reservation_id` | UUID/string | No | Original Reservation identifier. |
| `owner_id` | UUID/string | No | Original owning Human User identifier. |
| `vehicle_id` | UUID/string | No | Original Vehicle identifier. |
| `facility_id` | UUID/string | No | Facility containing the Connector. |
| `station_id` | UUID/string | No | Charging Station containing the Connector. |
| `connector_id` | UUID/string | No | Original Connector identifier. |
| `status` | enum | No | `ACTIVE` or `COMPLETED`. |
| `started_at` | timestamp UTC | No | Session start timestamp. |
| `ended_at` | timestamp UTC | Yes | Session end timestamp. |
| `created_at` | timestamp UTC | No | Persistence creation timestamp. |
| `updated_at` | timestamp UTC | No | Last update timestamp. |

### 11.1.3 Research Schema

The Research schema uses the same columns and logical types, with these transformations:

| Column | Research Transformation |
|---|---|
| `session_id` | Pseudonymized in namespace `charging_session`. |
| `reservation_id` | Pseudonymized in namespace `reservation`. |
| `owner_id` | Pseudonymized in namespace `owner`. |
| `vehicle_id` | Pseudonymized in namespace `vehicle`. |
| `facility_id` | Preserved. |
| `station_id` | Preserved. |
| `connector_id` | Preserved. |

Infrastructure identifiers are preserved because facility, station and connector analysis is a primary research use case and these identifiers are not direct Human identifiers.

### 11.1.4 Ordering

Rows shall be ordered by:

```text
started_at ASC
session_id ASC
```

---

## 11.2 `OPERATIONAL_TELEMETRY`

### 11.2.1 Selection Rules

A Telemetry Sample shall be selected when:

```text
recorded_at >= from
AND
recorded_at < to
```

The export shall additionally apply:

- authorized Facility scope through the associated Charging Session and Connector;
- optional Facility filter;
- optional Station filter;
- optional Connector filter;
- optional `session_id` filter;
- `data_cutoff_at`.

Telemetry shall remain linked to its associated Charging Session.

### 11.2.2 Administrative Schema

| Column | Type | Nullable | Description |
|---|---|---:|---|
| `telemetry_sample_id` | UUID/string | No | Original platform Telemetry Sample identifier. |
| `sample_id` | string | No | Producer-defined idempotency identifier. |
| `source` | enum | No | `SIMULATOR` or `API_CLIENT`. |
| `session_id` | UUID/string | No | Original Charging Session identifier. |
| `reservation_id` | UUID/string | No | Reservation associated with the session. |
| `owner_id` | UUID/string | No | Owning Human User identifier. |
| `vehicle_id` | UUID/string | No | Vehicle associated with the session. |
| `facility_id` | UUID/string | No | Facility containing the Connector. |
| `station_id` | UUID/string | No | Charging Station containing the Connector. |
| `connector_id` | UUID/string | No | Connector associated with the session. |
| `session_status` | enum | No | Associated Charging Session status. |
| `session_started_at` | timestamp UTC | No | Associated session start timestamp. |
| `session_ended_at` | timestamp UTC | Yes | Associated session end timestamp. |
| `recorded_at` | timestamp UTC | No | Time the observation was produced. |
| `received_at` | timestamp UTC | No | Time the platform received the observation. |
| `power_kw` | decimal | Yes | Instantaneous charging power. |
| `energy_kwh` | decimal | Yes | Accumulated delivered energy. |
| `state_of_charge_percent` | decimal | Yes | Battery state of charge from `0` to `100`. |
| `created_at` | timestamp UTC | No | Telemetry persistence timestamp. |

### 11.2.3 Research Schema

The Research schema uses the same columns and logical types, with these transformations:

| Column | Research Transformation |
|---|---|
| `telemetry_sample_id` | Pseudonymized in namespace `telemetry_sample`. |
| `sample_id` | Pseudonymized in namespace `producer_sample`. |
| `session_id` | Pseudonymized in namespace `charging_session`. |
| `reservation_id` | Pseudonymized in namespace `reservation`. |
| `owner_id` | Pseudonymized in namespace `owner`. |
| `vehicle_id` | Pseudonymized in namespace `vehicle`. |
| `facility_id` | Preserved. |
| `station_id` | Preserved. |
| `connector_id` | Preserved. |

Within the artifact, all rows belonging to the same Charging Session shall contain the same pseudonymous `session_id`, `reservation_id`, `owner_id` and `vehicle_id`.

### 11.2.4 Missing Measurements

`power_kw`, `energy_kwh` and `state_of_charge_percent` are independently optional.

The exporter shall preserve missing values as null.

It shall not:

- interpolate values;
- infer zero;
- forward-fill;
- backward-fill;
- derive energy from power;
- derive power from energy.

### 11.2.5 Ordering

Rows shall be ordered by:

```text
recorded_at ASC
received_at ASC
telemetry_sample_id ASC
```

---

## 11.3 `ANALYTICAL_OCCUPANCY`

### 11.3.1 Source

This dataset shall reuse the Occupancy projection defined by SPEC-010.

It shall not independently implement occupancy formulas.

### 11.3.2 Required Parameters

`ANALYTICAL_OCCUPANCY` requires:

- `from`;
- `to`;
- `granularity`;
- a resolvable timezone according to SPEC-010.

Supported granularities are:

```text
hour
day
week
month
```

### 11.3.3 Scope

The dataset may be scoped by:

- Facility;
- Charging Station;
- Connector.

Filter hierarchy and cross-Facility timezone rules shall follow SPEC-010.

### 11.3.4 Schema

| Column | Type | Nullable | Description |
|---|---|---:|---|
| `bucket_from` | timestamp with offset | No | Inclusive bucket start. |
| `bucket_to` | timestamp with offset | No | Exclusive bucket end. |
| `timezone` | string | No | IANA timezone used for aggregation. |
| `facility_id` | UUID/string | Yes | Requested Facility scope, when singular. |
| `station_id` | UUID/string | Yes | Requested Station scope. |
| `connector_id` | UUID/string | Yes | Requested Connector scope. |
| `available_duration_minutes` | decimal | No | Operational Capacity in the bucket. |
| `reserved_duration_minutes` | decimal | No | Reserved Duration in the bucket. |
| `charging_duration_minutes` | decimal | No | Charging Duration in the bucket. |
| `effective_reserved_charging_duration_minutes` | decimal | No | Charging overlap with reserved time. |
| `unused_reserved_duration_minutes` | decimal | No | Reserved Duration not effectively used. |
| `reserved_occupancy_rate` | decimal | Yes | Reserved Occupancy rate from `0` to `1`. |
| `effective_occupancy_rate` | decimal | Yes | Effective Occupancy rate from `0` to `1`. |
| `reserved_time_utilization_rate` | decimal | Yes | Utilization of reserved time from `0` to `1`. |

Rates shall be null when their denominator is zero, as defined by SPEC-010.

### 11.3.5 Profile Behavior

Administrative and Research schemas are identical for `ANALYTICAL_OCCUPANCY`.

No Human, Vehicle, Reservation or Charging Session identifiers are exported.

### 11.3.6 Ordering

Rows shall be ordered by:

```text
bucket_from ASC
bucket_to ASC
```

---

# 12. Export Filters

## 12.1 Common Filters

| Filter | Required | Applicable Dataset Types | Description |
|---|---:|---|---|
| `from` | Yes | All | Inclusive lower boundary. |
| `to` | Yes | All | Exclusive upper boundary. |
| `facility_id` | No | All | Restricts the export to one Facility. |
| `station_id` | No | All | Restricts the export to one Charging Station. |
| `connector_id` | No | All | Restricts the export to one Connector. |
| `timezone` | Conditional | Analytical | IANA timezone used for aggregation and bucket presentation. |
| `granularity` | Required | `ANALYTICAL_OCCUPANCY` | `hour`, `day`, `week` or `month`. |
| `session_id` | No | `OPERATIONAL_TELEMETRY` | Restricts telemetry to one Charging Session. |

## 12.2 Time Window

The Export Window shall use:

```text
[from, to)
```

Both timestamps shall include an explicit timezone offset.

The server shall normalize operational selection boundaries to UTC.

`from` shall be earlier than `to`.

## 12.3 Filter Hierarchy

When multiple infrastructure filters are provided:

- Connector shall belong to Station;
- Station shall belong to Facility;
- Charging Session shall belong to the resolved Connector scope.

Mismatched combinations shall return `400 Bad Request`.

## 12.4 Unsupported Filters

Filters not supported by the selected Dataset Type shall return `422 Unprocessable Entity`.

## 12.5 Empty Results

An authorized export that matches no records shall complete successfully.

The artifact shall contain:

- a valid manifest;
- a data file containing the CSV header only or an empty Parquet table;
- `row_count` equal to `0`.

---

# 13. Snapshot and Data Cutoff

## 13.1 Cutoff Assignment

The platform shall assign `data_cutoff_at` when the export request is accepted.

The client shall not provide `data_cutoff_at`.

`data_cutoff_at` shall be persisted in UTC.

## 13.2 Snapshot Rule

Generation shall evaluate source data as of the assigned `data_cutoff_at`.

At minimum:

- source records created after the cutoff shall be excluded;
- source state changes after the cutoff shall not produce a mixed or partially newer artifact;
- all files and manifest metadata shall represent one logically consistent generation snapshot.

The implementation may use a database transaction snapshot, temporal predicates or an equivalent consistency mechanism.

## 13.3 Late-Arriving Telemetry

A Telemetry Sample with `recorded_at` inside the Export Window but `received_at` after `data_cutoff_at` shall not be included.

This rule ensures that the artifact can be reproduced from the source state available at the cutoff.

## 13.4 Analytical Snapshot

`ANALYTICAL_OCCUPANCY` shall be computed using the same source boundary.

The exporter shall ensure that all buckets use one consistent cutoff.

---

# 14. Dataset Export Lifecycle

Dataset generation is represented by a persistent Dataset Export resource.

```text
POST /dataset-exports
          │
          ▼
       PENDING
          │
          ▼
      PROCESSING
       │       │
       ▼       ▼
  COMPLETED   FAILED
```

## 14.1 States

### PENDING

The request has been accepted and persisted.

Generation has not started.

### PROCESSING

Generation is executing.

No artifact is available for download.

### COMPLETED

Generation completed successfully.

Artifact metadata is available.

The artifact may be downloaded while retained.

### FAILED

Generation failed.

No successful artifact shall be exposed.

## 14.2 Valid Transitions

| Current | Next |
|---|---|
| `PENDING` | `PROCESSING` |
| `PROCESSING` | `COMPLETED` |
| `PROCESSING` | `FAILED` |

No other transition is valid.

## 14.3 Terminal Immutability

`COMPLETED` and `FAILED` are terminal.

A failed export shall not automatically return to `PENDING`.

A retry shall create a new Dataset Export resource.

## 14.4 Process Restart Recovery

The implementation shall prevent Dataset Export resources from remaining indefinitely in `PROCESSING`.

On startup or through an equivalent recovery mechanism, abandoned work shall be:

- safely resumed; or
- transitioned to `FAILED` with an operational failure code.

This requirement does not mandate a worker technology.

## 14.5 Artifact Expiration

Artifact expiration shall not change `COMPLETED` to a new lifecycle state.

Artifact availability shall be represented separately.

---

# 15. Dataset Export Resource

A Dataset Export shall persist at least:

| Field | Description |
|---|---|
| `id` | Unique Dataset Export identifier. |
| `requested_by` | Authenticated Human User identifier. |
| `dataset_type` | Requested Dataset Type. |
| `export_profile` | Requested Export Profile. |
| `format` | Requested data format. |
| `filters` | Canonical validated filter object. |
| `status` | Lifecycle state. |
| `data_cutoff_at` | Snapshot boundary. |
| `schema_version` | Resolved schema version. |
| `created_at` | Request acceptance timestamp. |
| `started_at` | Processing start timestamp. |
| `completed_at` | Successful completion timestamp. |
| `failed_at` | Failure timestamp. |
| `failure_code` | Stable diagnostic code when failed. |
| `failure_message` | Sanitized operational message when failed. |
| `row_count` | Generated row count when completed. |
| `data_file_sha256` | SHA-256 of the uncompressed data file. |
| `artifact_sha256` | SHA-256 of the final ZIP artifact. |
| `artifact_size_bytes` | Final artifact size. |
| `artifact_storage_key` | Internal storage reference. |
| `artifact_expires_at` | Artifact retention boundary. |

`artifact_storage_key` shall never be exposed as a public filesystem path or storage-provider URL.

---

# 16. Artifact Structure

A completed export shall produce one ZIP archive.

```text
dataset-export-{export_id}.zip
├── manifest.json
└── data.csv
```

or:

```text
dataset-export-{export_id}.zip
├── manifest.json
└── data.parquet
```

Version 1 shall not produce multiple data files.

The ZIP entry names shall be stable:

```text
manifest.json
data.csv
data.parquet
```

The archive shall not contain:

- absolute paths;
- parent-directory traversal entries;
- temporary files;
- pseudonym lookup tables;
- credentials;
- internal logs.

---

# 17. Manifest Contract

## 17.1 Mandatory Fields

`manifest.json` shall contain:

| Field | Description |
|---|---|
| `dataset_export_id` | Dataset Export identifier. |
| `dataset_type` | Dataset Type. |
| `dataset_category` | `OPERATIONAL` or `ANALYTICAL`. |
| `export_profile` | `ADMINISTRATIVE` or `RESEARCH`. |
| `schema_version` | Data schema version. |
| `format` | `CSV` or `PARQUET`. |
| `generated_at` | Artifact generation timestamp in UTC. |
| `data_cutoff_at` | Snapshot boundary in UTC. |
| `application_version` | Backend application version. |
| `source_revision` | Source control revision, when available. |
| `filters` | Canonical validated filters. |
| `columns` | Ordered logical column descriptions. |
| `row_count` | Number of data rows. |
| `data_file` | Data entry name. |
| `data_file_size_bytes` | Uncompressed data-file size. |
| `data_file_sha256` | SHA-256 of the uncompressed data file. |
| `pseudonymization` | Profile and scope metadata without secret material. |
| `simulation_seed` | Simulation seed when the selected data source provides one; otherwise null. |

## 17.2 Example

```json
{
  "dataset_export_id": "0d80cb12-a738-4c4d-a315-2e72c7d3b5e1",
  "dataset_type": "OPERATIONAL_TELEMETRY",
  "dataset_category": "OPERATIONAL",
  "export_profile": "RESEARCH",
  "schema_version": "1.0.0",
  "format": "PARQUET",
  "generated_at": "2026-08-15T18:23:41Z",
  "data_cutoff_at": "2026-08-15T18:23:00Z",
  "application_version": "1.7.0",
  "source_revision": "a82d0a5",
  "filters": {
    "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
    "station_id": null,
    "connector_id": null,
    "session_id": null,
    "from": "2026-08-01T00:00:00Z",
    "to": "2026-08-15T00:00:00Z",
    "timezone": null,
    "granularity": null
  },
  "columns": [
    {
      "name": "telemetry_sample_id",
      "type": "string",
      "nullable": false,
      "unit": null
    },
    {
      "name": "power_kw",
      "type": "decimal",
      "nullable": true,
      "unit": "kW"
    }
  ],
  "row_count": 18425,
  "data_file": "data.parquet",
  "data_file_size_bytes": 482150,
  "data_file_sha256": "sha256:26d9...",
  "pseudonymization": {
    "applied": true,
    "scope": "DATASET_EXPORT",
    "algorithm_identifier": "HMAC_SHA256_V1"
  },
  "simulation_seed": null
}
```

## 17.3 Checksum Rules

`data_file_sha256` shall be calculated over the exact uncompressed bytes of `data.csv` or `data.parquet`.

The final ZIP artifact checksum shall be stored in Dataset Export metadata and exposed by the resource API.

The ZIP checksum shall not be embedded inside `manifest.json`, because embedding a checksum of an artifact inside that same artifact would create a self-referential value.

## 17.4 Manifest Ordering

JSON object ordering is not semantically significant.

The `columns` array order shall match the data-file column order.

## 17.5 Sensitive Metadata

The manifest shall not expose:

- pseudonymization keys;
- original-to-pseudonymous mappings;
- database connection information;
- internal storage paths;
- stack traces;
- secrets.

---

# 18. Reproducibility

A completed export shall record enough information to understand and validate its generation.

Equivalent Dataset Export requests evaluated against equivalent source state shall produce logically equivalent data.

Logical equivalence requires:

- identical selected records;
- identical field transformations;
- identical null behavior;
- identical numeric values;
- identical row ordering;
- identical schema version.

Byte-for-byte ZIP equality is not required because ZIP metadata and compression output may vary.

The following values shall support provenance:

- Dataset Type;
- Export Profile;
- schema version;
- canonical filters;
- data cutoff;
- application version;
- source revision;
- row count;
- data-file checksum;
- simulation seed when available.

Dataset Export does not guarantee that a historical artifact can be regenerated after source records or application versions are permanently removed. It guarantees that the original artifact is self-describing and integrity-checkable.

---

# 19. Storage Model

Dataset Export metadata shall be stored in PostgreSQL.

Artifact bytes shall be stored outside PostgreSQL through a `DatasetArtifactStorage` abstraction.

```text
DatasetExport metadata
        │
        ▼
   PostgreSQL

Dataset ZIP bytes
        │
        ▼
DatasetArtifactStorage
```

The storage abstraction shall support at least:

- store artifact;
- open or stream artifact;
- check artifact existence;
- delete artifact.

The initial implementation may use:

- a local persistent directory;
- a mounted persistent volume.

Future implementations may use object storage without changing the REST contract.

Artifact writes shall be atomic from the perspective of download requests.

A partially written artifact shall never be downloadable.

---

# 20. Artifact Retention

Generated artifacts shall remain available until `artifact_expires_at`.

After expiration:

- the Dataset Export resource shall remain queryable;
- manifest-derived metadata shall remain queryable;
- the artifact may be deleted;
- download shall return `410 Gone`.

Retention cleanup may execute lazily or through scheduled operational maintenance.

Expiration shall be evaluated using server time in UTC.

Metadata retention is not limited by artifact retention in Version 1.

---

# 21. Operational Configuration

The implementation shall support deployment configuration for:

- maximum export window;
- maximum row count;
- maximum artifact size;
- maximum concurrent processing exports;
- artifact retention period;
- enabled formats;
- artifact storage location;
- abandoned-processing timeout;
- pseudonymization secret.

These values may be provided through the platform's existing configuration mechanism.

The specification does not require a particular environment-variable library or configuration provider.

## 21.1 Suggested Configuration Keys

The implementation may use names equivalent to:

```text
DATASET_EXPORT_MAX_WINDOW_DAYS
DATASET_EXPORT_MAX_ROWS
DATASET_EXPORT_MAX_ARTIFACT_SIZE_BYTES
DATASET_EXPORT_MAX_CONCURRENT_JOBS
DATASET_EXPORT_RETENTION_DAYS
DATASET_EXPORT_ENABLED_FORMATS
DATASET_EXPORT_STORAGE_PATH
DATASET_EXPORT_PROCESSING_TIMEOUT_SECONDS
DATASET_EXPORT_PSEUDONYMIZATION_SECRET
```

These names are implementation guidance rather than public API contracts.

## 21.2 Domain Semantics Excluded from Configuration

Deployment configuration shall not change:

- Dataset Type meanings;
- Export Profile meanings;
- schema columns;
- pseudonymization namespaces;
- occupancy formulas;
- time-window inclusivity;
- row ordering;
- lifecycle transitions.

---

# 22. Operational Limits

Requests shall be rejected before work is scheduled whenever the violation can be determined from request parameters.

Possible pre-generation violations include:

- invalid window;
- unsupported format;
- disabled format;
- unsupported filter;
- unauthorized scope;
- configured concurrency limit;
- configured time-window limit.

Limits discovered during generation include:

- maximum row count;
- maximum artifact size;
- processing timeout.

When a runtime limit is exceeded, the export shall transition to `FAILED`.

The failure shall use a stable `failure_code`, such as:

```text
ROW_LIMIT_EXCEEDED
ARTIFACT_SIZE_LIMIT_EXCEEDED
PROCESSING_TIMEOUT
STORAGE_FAILURE
GENERATION_FAILURE
```

Failure messages shall be sanitized and shall not expose stack traces, SQL or filesystem paths.

---

# 23. REST API

All endpoints require Bearer authentication.

## 23.1 Create Dataset Export

```http
POST /dataset-exports
```

### Request

```json
{
  "dataset_type": "OPERATIONAL_TELEMETRY",
  "export_profile": "RESEARCH",
  "format": "PARQUET",
  "filters": {
    "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
    "station_id": null,
    "connector_id": null,
    "session_id": null,
    "from": "2026-08-01T00:00:00Z",
    "to": "2026-08-15T00:00:00Z",
    "timezone": null,
    "granularity": null
  }
}
```

### Response

```http
202 Accepted
Location: /dataset-exports/0d80cb12-a738-4c4d-a315-2e72c7d3b5e1
```

```json
{
  "id": "0d80cb12-a738-4c4d-a315-2e72c7d3b5e1",
  "dataset_type": "OPERATIONAL_TELEMETRY",
  "export_profile": "RESEARCH",
  "format": "PARQUET",
  "status": "PENDING",
  "schema_version": "1.0.0",
  "data_cutoff_at": "2026-08-15T18:23:00Z",
  "created_at": "2026-08-15T18:23:00Z"
}
```

The endpoint shall return after the request and metadata are persisted.

Dataset generation shall not block the HTTP response until completion.

## 23.2 List Dataset Exports

```http
GET /dataset-exports
```

Supported query parameters:

| Parameter | Required | Description |
|---|---:|---|
| `status` | No | Filters by lifecycle state. |
| `dataset_type` | No | Filters by Dataset Type. |
| `export_profile` | No | Filters by Export Profile. |
| `created_from` | No | Inclusive creation timestamp. |
| `created_to` | No | Exclusive creation timestamp. |
| `limit` | No | Page size. |
| `offset` | No | Page offset. |

The response shall contain only resources visible to the authenticated actor.

Example:

```json
{
  "items": [
    {
      "id": "0d80cb12-a738-4c4d-a315-2e72c7d3b5e1",
      "dataset_type": "OPERATIONAL_TELEMETRY",
      "export_profile": "RESEARCH",
      "format": "PARQUET",
      "status": "COMPLETED",
      "row_count": 18425,
      "artifact_available": true,
      "created_at": "2026-08-15T18:23:00Z",
      "completed_at": "2026-08-15T18:23:41Z"
    }
  ],
  "limit": 50,
  "offset": 0,
  "total": 1
}
```

Default and maximum page sizes are implementation configurable and shall be documented in OpenAPI.

## 23.3 Retrieve Dataset Export

```http
GET /dataset-exports/{dataset_export_id}
```

Example completed response:

```json
{
  "id": "0d80cb12-a738-4c4d-a315-2e72c7d3b5e1",
  "requested_by": "c182998e-094d-4ad8-b8ee-e996f2437b79",
  "dataset_type": "OPERATIONAL_TELEMETRY",
  "dataset_category": "OPERATIONAL",
  "export_profile": "RESEARCH",
  "format": "PARQUET",
  "status": "COMPLETED",
  "schema_version": "1.0.0",
  "filters": {
    "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
    "station_id": null,
    "connector_id": null,
    "session_id": null,
    "from": "2026-08-01T00:00:00Z",
    "to": "2026-08-15T00:00:00Z",
    "timezone": null,
    "granularity": null
  },
  "data_cutoff_at": "2026-08-15T18:23:00Z",
  "created_at": "2026-08-15T18:23:00Z",
  "started_at": "2026-08-15T18:23:01Z",
  "completed_at": "2026-08-15T18:23:41Z",
  "failed_at": null,
  "failure_code": null,
  "failure_message": null,
  "row_count": 18425,
  "data_file_sha256": "sha256:26d9...",
  "artifact_sha256": "sha256:98a1...",
  "artifact_size_bytes": 271932,
  "artifact_available": true,
  "artifact_expires_at": "2026-09-14T18:23:41Z"
}
```

The API shall not expose the internal storage key.

## 23.4 Download Dataset Artifact

```http
GET /dataset-exports/{dataset_export_id}/download
```

Successful response:

```http
200 OK
Content-Type: application/zip
Content-Disposition: attachment; filename="dataset-export-0d80cb12-a738-4c4d-a315-2e72c7d3b5e1.zip"
ETag: "sha256:98a1..."
```

The implementation should stream the artifact rather than load the complete ZIP into application memory.

Download is permitted only when:

- status is `COMPLETED`;
- the actor may access the Dataset Export;
- the artifact exists;
- the artifact has not expired.

## 23.5 Idempotency

`POST /dataset-exports` may accept the existing platform `Idempotency-Key` convention when available.

Idempotency shall protect client retries from accidentally creating duplicate resources.

Two identical requests without the same idempotency key may create two independent Dataset Export resources with different:

- identifiers;
- data cutoffs;
- pseudonyms;
- artifacts.

---

# 24. HTTP Status Codes

| Status | Meaning |
|---|---|
| `200 OK` | List, metadata retrieval or artifact download succeeded. |
| `202 Accepted` | Export request was accepted. |
| `400 Bad Request` | Invalid window, hierarchy, timezone or incompatible parameters. |
| `401 Unauthorized` | Authentication is missing or invalid. |
| `403 Forbidden` | Actor or Facility scope is not authorized. |
| `404 Not Found` | Dataset Export or requested scoped resource does not exist. |
| `409 Conflict` | Artifact is not downloadable in the current lifecycle state or concurrency prevents acceptance. |
| `410 Gone` | Completed artifact expired or was removed according to retention. |
| `422 Unprocessable Entity` | Request schema, Dataset Type, format, profile or filter combination is unsupported. |

A `FAILED` Dataset Export remains retrievable through `GET /dataset-exports/{id}`.

---

# 25. Authorization

Dataset Export shall reuse the roles and account model defined by SPEC-005.

This specification introduces no new Role and no new account type.

## 25.1 Platform Administrator

A `PlatformAdministrator` may:

- create Administrative or Research exports;
- export any authorized Dataset Type;
- export one Facility or cross-Facility scope;
- list and retrieve all Dataset Export resources;
- download all retained artifacts.

Cross-Facility analytical exports shall require an explicit timezone, consistent with SPEC-010.

## 25.2 Facility Operator

A `FacilityOperator` may:

- create Administrative or Research exports for assigned Facilities;
- list and retrieve exports created by that user;
- download artifacts created by that user.

A Facility Operator shall not:

- export cross-Facility scope;
- access Facilities outside explicit assignments;
- access another user's Dataset Export resource.

The server shall enforce Facility scope independently from request filters.

## 25.3 Researcher

A `Researcher` may:

- create only `RESEARCH` exports;
- use only explicitly authorized Facility scope;
- list and retrieve exports created by that user;
- download artifacts created by that user.

A Researcher shall not create `ADMINISTRATIVE` exports.

Because SPEC-005 does not define Facility Assignments for Researchers, Version 1 grants a Researcher platform-wide Research export scope unless a future specification introduces a narrower assignment model.

This access decision shall be explicit in implementation authorization policy and documented in OpenAPI.

## 25.4 Data Scientist

A `DataScientist` has the same Dataset Export permissions as a Researcher in Version 1.

A future Predictions specification may grant additional prediction-related permissions without changing this Dataset Export profile rule.

## 25.5 Other Actors

The following actors shall not access Dataset Export in Version 1:

- `EVDriver`;
- `TechnicalClient`;
- inactive accounts;
- Human Users without one of the roles explicitly permitted above.

## 25.6 Resource Visibility

Platform Administrators may view all Dataset Export resources.

Other authorized roles may view only Dataset Export resources they requested.

Authorization shall be checked:

- when creating the request;
- when retrieving metadata;
- when listing resources;
- when downloading the artifact.

A previously generated artifact shall not bypass current account-status checks.

---

# 26. Security and Privacy

Dataset Export shall apply defense in depth.

The implementation shall:

- validate all request parameters;
- enforce authorized Facility scope server-side;
- avoid logging complete dataset rows;
- avoid logging pseudonymization secrets;
- prevent path traversal in storage keys and ZIP entries;
- generate non-public storage keys;
- avoid exposing internal storage locations;
- use constant-time or library-provided cryptographic primitives for pseudonymization;
- prevent formula injection in CSV spreadsheet consumers.

For CSV, string fields beginning with spreadsheet formula prefixes:

```text
=
+
-
@
```

shall be escaped or otherwise safely serialized according to a documented policy when they can originate from untrusted source text.

Version 1 schemas contain primarily controlled identifiers and enumerations, but the protection shall be applied by the reusable CSV serializer.

---

# 27. Observability

Dataset Export shall integrate with the existing platform observability model.

## 27.1 Metrics

At minimum, expose:

- export requests by Dataset Type, Profile and Format;
- accepted exports;
- rejected exports;
- completed exports;
- failed exports;
- processing duration;
- queue or pending duration;
- generated row count;
- artifact size;
- currently processing export count;
- expired artifact count;
- storage operation failures.

Metrics shall avoid high-cardinality labels such as:

- Dataset Export identifiers;
- actor identifiers;
- Facility identifiers;
- Station identifiers;
- Connector identifiers.

## 27.2 Structured Logs

Structured logs shall be emitted for:

- request accepted;
- processing started;
- processing completed;
- processing failed;
- artifact stored;
- artifact expired or deleted;
- authorization failure;
- validation failure;
- recovery of abandoned processing.

Logs may include Dataset Export identifier for correlation.

Logs shall not include:

- complete dataset rows;
- original-to-pseudonymous mappings;
- secrets;
- SQL statements containing sensitive values;
- stack traces in client-facing responses.

## 27.3 Tracing

Long-running generation shall preserve trace correlation when supported by the selected execution mechanism.

The implementation may create a new internal trace for background execution linked to the originating request trace.

---

# 28. OpenAPI Requirements

Generated OpenAPI documentation shall include:

- Dataset Type enum;
- Dataset Category enum;
- Export Profile enum;
- Export Format enum;
- lifecycle status enum;
- common filter schema;
- dataset-specific filter validation;
- create request and response schemas;
- list response schema;
- detail response schema;
- download response;
- authorization notes;
- error responses;
- examples for all supported Dataset Types.

Bearer authentication shall be declared for all endpoints.

OpenAPI shall document:

- `[from, to)` semantics;
- required timezone offsets;
- analytical timezone behavior;
- role/profile restrictions;
- artifact expiration behavior;
- asynchronous lifecycle behavior.

---

# 29. Persistence and Migration Requirements

The implementation shall create persistence for Dataset Export metadata.

Database migrations shall:

- create required tables and constraints;
- create indexes required for lifecycle and ownership queries;
- remain reversible according to the repository migration conventions.

Recommended indexes include:

- `status`;
- `requested_by`;
- `created_at`;
- `(requested_by, created_at)`;
- `(status, created_at)`;
- `artifact_expires_at`.

The implementation shall enforce valid lifecycle status values.

A unique constraint on request content is not required.

Identical requests may produce independent exports.

---

# 30. Testing Requirements

## 30.1 Unit Tests

Unit tests shall cover:

- Dataset Type validation;
- profile validation;
- format validation;
- filter validation;
- filter hierarchy;
- lifecycle transitions;
- schema version resolution;
- deterministic row ordering;
- UTC timestamp serialization;
- CSV null behavior;
- CSV escaping;
- manifest generation;
- data-file checksum generation;
- pseudonym determinism inside one export;
- namespace separation;
- different pseudonyms across separate exports;
- Research field transformations;
- failure-code mapping.

## 30.2 Integration Tests

Integration tests shall cover:

- metadata persistence;
- export execution;
- snapshot cutoff behavior;
- late-arriving Telemetry exclusion;
- Charging Session selection;
- Telemetry-to-session linkage;
- Analytics occupancy reuse;
- artifact atomic storage;
- artifact retrieval;
- artifact deletion;
- abandoned-processing recovery;
- configured row limit;
- configured artifact-size limit.

## 30.3 API Tests

API tests shall cover:

- successful export creation;
- immediate `202 Accepted`;
- lifecycle polling;
- completed export retrieval;
- failed export retrieval;
- list pagination and filtering;
- download before completion;
- successful download;
- expired download;
- missing artifact;
- invalid Dataset Type;
- invalid Profile;
- disabled Format;
- unsupported filter;
- invalid window;
- mismatched infrastructure hierarchy;
- unauthorized Facility;
- role/profile restrictions;
- inactive-account rejection;
- resource visibility between users.

## 30.4 Format Compatibility Tests

For equivalent source state and request parameters, CSV and Parquet shall contain logically equivalent:

- columns;
- rows;
- null values;
- timestamps;
- decimal values;
- enumerations.

## 30.5 Contract Tests

Contract tests shall validate:

- ZIP entry names;
- absence of unsafe ZIP paths;
- manifest mandatory fields;
- manifest column order;
- schema version;
- row count;
- data-file checksum;
- deterministic ordering.

---

# 31. Acceptance Criteria

## Architecture

- Dataset Export is implemented as a distinct Backend API module.
- AI Research Environment does not access PostgreSQL directly.
- No model training or feature engineering is added to the Backend API.
- Execution technology is not exposed through the public API.
- Artifact storage is abstracted from application logic.

## Dataset Types

- `OPERATIONAL_CHARGING_SESSIONS` is implemented.
- `OPERATIONAL_TELEMETRY` is implemented.
- `ANALYTICAL_OCCUPANCY` is implemented.
- Dataset schemas match this specification.
- Dataset schemas are versioned.

## Profiles and Privacy

- `ADMINISTRATIVE` and `RESEARCH` profiles are implemented.
- Research exports pseudonymize required sensitive identifiers.
- Referential integrity is preserved inside each artifact.
- Pseudonym lookup data is not exported.
- Role/profile authorization is enforced.

## Lifecycle

- Creation returns `202 Accepted`.
- Generation is decoupled from the request.
- Valid lifecycle transitions are enforced.
- Terminal states are immutable.
- Abandoned processing is recoverable or failed deterministically.
- Failure information is sanitized.

## Snapshot and Reproducibility

- `data_cutoff_at` is assigned by the server.
- One logical snapshot is used per export.
- Late-arriving Telemetry after the cutoff is excluded.
- Row ordering is deterministic.
- Manifest provenance fields are populated.
- Data-file checksum is valid.

## Artifacts

- A completed export produces one ZIP.
- ZIP contains `manifest.json` and exactly one data file.
- CSV and Parquet are supported when enabled.
- Partial artifacts are not downloadable.
- Artifact checksum and size are exposed through metadata.
- Expired artifacts return `410 Gone`.

## Authorization

- Platform Administrator permissions are implemented.
- Facility Operator scope is enforced.
- Researcher permissions are implemented.
- Data Scientist permissions are implemented.
- EV Drivers and Technical Clients are denied.
- Non-administrators see only their own Dataset Export resources.

## Documentation and Quality

- OpenAPI is complete.
- Observability requirements are implemented.
- Database migrations are included.
- Automated tests cover required scenarios.
- Existing operational and Analytics behavior remains unchanged.

---

# 32. Future Extensions

Potential future extensions include:

- additional operational datasets;
- Reservation datasets;
- energy datasets;
- Domain Event datasets;
- multi-file dataset bundles;
- shared pseudonymization across bundle files;
- scheduled exports;
- incremental exports;
- dataset partitioning;
- cloud object storage;
- signed artifacts;
- encrypted artifacts;
- dataset catalog APIs;
- feature-ready datasets;
- explicit research-scope assignments;
- simulation-run and experiment identifiers;
- tighter integration with Predictions.

These extensions shall preserve the architectural separation established by ADR-008.

---

# 33. Architectural Alignment

This specification operationalizes ADR-008 by defining the controlled dataset boundary between the transactional Backend API and the independent AI Research Environment.

It also aligns with:

- SPEC-005, by reusing existing Roles and authentication;
- SPEC-007, by preserving Charging Session semantics;
- SPEC-008, by preserving immutable Telemetry observations and missing measurements;
- SPEC-010, by reusing occupancy metrics, timezone behavior and analytical scope rules.

No additional ADR is required for Version 1 because:

- separation of AI experimentation is already decided by ADR-008;
- this specification leaves worker and storage technologies replaceable;
- operational configuration does not establish a new irreversible architectural constraint.

A future ADR may be justified if the platform adopts a specific distributed job system, external object storage provider or centralized dynamic configuration service.
