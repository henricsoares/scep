# SPEC-012 — Weekly Occupancy Predictions

## Smart Charging Experimentation Platform (SCEP)

**Document Status:** Draft / Under Review

**Implementation Status:** Planned

**Recommended Implementation Sequence:** After SPEC-013

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

**Depends on:**

- SPEC-002 — Domain Model and Ubiquitous Language
- SPEC-003 — Facilities
- SPEC-004 — Charging Stations
- SPEC-005 — Identity and Access
- SPEC-010 — Analytics
- SPEC-011 — Dataset Export
- ADR-008 — Separate AI Experimentation from the Transactional Platform

**Related planning:**

- SPEC-013 — Digital Twin Simulation Engine
- [GitHub issue #46](https://github.com/henricsoares/scep/issues/46) — research Roles and non-human
  actor authorization
- [GitHub issue #47](https://github.com/henricsoares/scep/issues/47) — this specification

---

# 1. Purpose

This specification defines the Version 1 contract for publishing, validating, persisting and
consuming externally generated recurring Weekly Occupancy Predictions.

One accepted publication represents exactly one complete recurring weekly occupancy profile for
exactly one Facility, Charging Station or Connector scope. The profile contains exactly:

```text
7 days × 24 hours = 168 hourly buckets
```

The external AI Research Environment performs feature engineering, model training, model
evaluation, inference and prediction generation. The Backend API validates and stores completed
prediction publications and exposes controlled read contracts.

The Backend API shall not train models and shall not execute model inference.

---

# 2. Status and Implementation Sequence

SPEC-012 may be approved before SPEC-013 is implemented. It has no mandatory runtime dependency on
the Digital Twin Simulation Engine.

Implementation and reference validation are intentionally deferred until:

- the research-role and non-human actor authorization debt is resolved;
- SPEC-013 can produce representative synthetic operational data; and
- the first external occupancy experiment can validate the publication integration.

The recommended sequence is:

1. approve SPEC-012;
2. define and implement SPEC-013;
3. generate representative synthetic operational data;
4. export a reference dataset;
5. execute the first external occupancy prediction experiment;
6. implement and validate SPEC-012.

This sequence is a delivery and validation decision, not a runtime dependency from Predictions to
the Simulation Engine.

---

# 3. Goals

Version 1 shall:

- define one unambiguous recurring weekly occupancy target;
- accept only complete profiles containing 168 unique hourly buckets;
- support Facility, Station and Connector scopes;
- preserve Facility timezone and infrastructure hierarchy semantics;
- make prediction publication immutable, atomic and safe to retry;
- preserve publication history and expose one deterministic current publication per scope;
- expose administrative history, profile and point-lookup contracts;
- support EVDriver-facing Connector recommendations without promising availability;
- preserve Dataset Export provenance when supplied;
- keep AI execution outside the Backend API;
- make persistence, authorization, observability and test expectations explicit.

---

# 4. Scope

This specification includes:

- the `WeeklyOccupancyPredictionPublication` aggregate;
- recurring weekly and hourly semantics;
- `FACILITY`, `STATION` and `CONNECTOR` prediction scopes;
- exactly 168 prediction buckets per publication;
- the `expected_occupancy_rate` target;
- derived expected availability;
- model, run and Dataset Export references;
- validation, canonicalization and idempotency;
- immutable history and automatic current selection;
- authenticated REST APIs;
- provisional authorization boundaries;
- persistence and migration requirements;
- OpenAPI, observability and testing requirements.

## 4.1 Out of Scope

Version 1 shall not include:

- model training or inference execution in the Backend API;
- prediction for a specific future calendar date;
- real-time prediction or live queue estimation;
- intervals shorter than one hour;
- daily, monthly or seasonal prediction contracts;
- holiday, weather or traffic features in the Backend contract;
- route planning, distance ranking or pricing optimization;
- automatic Reservation creation;
- availability guarantees;
- per-user prediction;
- session-duration or energy-demand prediction;
- predictive maintenance or anomaly detection;
- model binaries, notebooks, checkpoints or training source code;
- a Model Registry or Feature Store;
- automatic model deployment, retraining or promotion;
- simulation execution;
- creation or ownership of EVDriver-to-Facility eligibility relationships;
- unrelated frontend implementation.

---

# 5. Architectural Context

The Version 1 flow is:

```text
Operational or Synthetic Data
              │
              ▼
       Dataset Export
              │
              ▼
   AI Research Environment
   feature engineering, training,
   evaluation and inference
              │
              ▼
Authorized Prediction Publication API
              │
              ▼
 Weekly Occupancy Prediction Storage
              │
              ▼
 Administrative and EVDriver Queries
```

The AI Research Environment shall use Dataset Export artifacts and public APIs. It shall not access
PostgreSQL or internal module repositories directly.

Predictions owns accepted publication metadata and prediction buckets. It does not own or redefine:

- Facilities or their operating hours and timezone;
- Charging Stations or Connectors and their operational status;
- Reservations or Charging Sessions;
- Analytics formulas;
- Dataset Export artifacts;
- Human Roles, account types or infrastructure eligibility.

---

# 6. Ubiquitous Language

## 6.1 Weekly Occupancy Prediction

A recurring expected infrastructure-usage pattern indexed by local weekday and local hour. It is
not a forecast for one specific calendar date.

## 6.2 Weekly Occupancy Prediction Publication

The immutable aggregate that records one accepted complete profile, its scope, provenance and all
168 buckets. The canonical aggregate name is `WeeklyOccupancyPredictionPublication`.

## 6.3 Prediction Bucket

One typical local weekday/hour pattern within a publication.

## 6.4 Prediction Scope

Exactly one infrastructure hierarchy target identified by `scope_type` and its required Facility,
Station and Connector identifiers.

## 6.5 Current Publication

The accepted publication referenced for one canonical Prediction Scope because no prior current
publication existed or because its `generated_at` was strictly later than that of the prior current
publication. Acceptance time alone does not make a publication current.

## 6.6 Historical or Superseded Publication

An immutable accepted publication that is not current. It may have been replaced by a publication
with a later `generated_at`, or it may have remained historical at acceptance because its
`generated_at` was earlier than or equal to that of the existing current publication.

## 6.7 Authorized Prediction Publisher

An authenticated Human or non-human subject that a future SPEC-005-aligned permission mapping
authorizes to publish predictions. This normative concept is intentionally independent from the
current `TechnicalClient` account type.

## 6.8 Expected Occupancy Rate

The externally generated estimate of SPEC-010 `effective_occupancy_rate` for one recurring local
weekday/hour and Prediction Scope.

## 6.9 Expected Availability Rate

A presentation value derived as:

```text
expected_availability_rate = 1 - expected_occupancy_rate
```

It is not persisted as an independent prediction.

---

# 7. Prediction Target and Analytics Alignment

Version 1 selects SPEC-010 `effective_occupancy_rate` as its only predicted occupancy metric.

SPEC-010 defines:

```text
effective_occupancy_rate
=
charging_duration_minutes / available_duration_minutes
```

Therefore `expected_occupancy_rate` predicts actual Charging Session usage relative to Operational
Capacity. It does not predict `reserved_occupancy_rate`, Reservation commitments, instantaneous
Connector status or a newly invented occupancy measure.

Scope aggregation shall follow SPEC-010:

- Connector scope uses that Connector's Charging Duration and Available Duration;
- Station scope sums those durations over in-scope Connectors belonging to the Station before
  division;
- Facility scope sums those durations over in-scope Connectors belonging to Stations in the
  Facility before division.

The external AI workflow may engineer features freely, but observed target construction and later
comparison shall reuse the approved SPEC-010 formula, hierarchy, operating-hours rules and
timezone behavior. Predictions shall not reimplement an alternative Analytics formula.

SPEC-010 returns `null` when `available_duration_minutes` is zero. A publication nevertheless
contains all 168 recurring labels and requires a finite rate in every bucket. For a local bucket
with no Operational Capacity in an observed comparison window:

- there is no observable `effective_occupancy_rate` target for that occurrence;
- the published recurring rate shall not change that fact or create Operational Capacity;
- evaluation shall exclude the zero-denominator occurrence rather than interpret its observed
  value as zero; and
- EVDriver results shall exclude infrastructure that is closed or otherwise ineligible at query
  time.

This rule reconciles the complete recurring profile with SPEC-010's zero-denominator semantics.

---

# 8. Recurring Weekly Profile

Version 1 uses fixed values:

```text
prediction_type = WEEKLY_OCCUPANCY
cycle = WEEKLY
granularity = HOUR
```

Canonical weekday values and ordering are:

```text
MONDAY
TUESDAY
WEDNESDAY
THURSDAY
FRIDAY
SATURDAY
SUNDAY
```

`hour_of_day` shall be an integer from `0` through `23`.

Each publication shall contain exactly one bucket for every Cartesian pair of canonical weekday and
hour. A publication with a missing pair, a duplicate pair or any additional bucket shall be
rejected in full.

`hour_of_day = 18` represents the half-open local interval:

```text
[18:00, 19:00)
```

One bucket means "during a typical occurrence of this local weekday and hour." It does not identify
one future date and does not guarantee real-time or future availability.

Buckets in requests and responses shall use deterministic weekday-major, hour-minor ordering:

```text
MONDAY 00 ... MONDAY 23,
TUESDAY 00 ... TUESDAY 23,
...
SUNDAY 00 ... SUNDAY 23
```

Partial weekly publications are not supported in Version 1.

---

# 9. Bucket Contract

Each bucket shall contain exactly:

- `day_of_week`;
- `hour_of_day`;
- `expected_occupancy_rate`.

Example:

```json
{
  "day_of_week": "TUESDAY",
  "hour_of_day": 18,
  "expected_occupancy_rate": 0.72
}
```

This means that actual Charging Session usage is expected to consume 72% of Operational Capacity
during a typical Tuesday from 18:00 inclusive to 19:00 exclusive in the owning Facility timezone.

Validation rules are:

- `day_of_week` shall be one canonical uppercase enum value;
- `hour_of_day` shall be an integer in `[0, 23]`;
- `expected_occupancy_rate` shall be a finite JSON number;
- `0 <= expected_occupancy_rate <= 1`;
- `NaN`, positive or negative infinity and numeric strings shall be rejected;
- duplicate and missing weekday/hour pairs shall be rejected;
- the complete publication shall be validated before persistence begins.

The API may include `expected_availability_rate` in read responses. When included, it shall be
derived from the persisted occupancy value and shall not be accepted in publication requests.

---

# 10. Prediction Scope and Hierarchy

Supported `scope_type` values are:

```text
FACILITY
STATION
CONNECTOR
```

## 10.1 Facility Scope

- `facility_id` is required;
- `station_id` shall be absent;
- `connector_id` shall be absent.

## 10.2 Station Scope

- `facility_id` is required;
- `station_id` is required;
- `connector_id` shall be absent.

## 10.3 Connector Scope

- `facility_id` is required;
- `station_id` is required;
- `connector_id` is required.

Before acceptance, the Backend API shall validate that:

- the Facility exists;
- the Station exists and belongs to the Facility when supplied;
- the Connector exists and belongs to the Station when supplied;
- all hierarchy identifiers are mutually consistent; and
- the scope is eligible to receive a publication under the owning domain's current contract.

Facility, Station and Connector lifecycle and operational state remain owned by SPEC-003 and
SPEC-004. Prediction acceptance shall not silently activate, deactivate or otherwise mutate
infrastructure.

Hierarchy identifiers stored in an accepted publication are historical scope references. A later
operational status change does not mutate or invalidate publication history.

---

# 11. Timezone and Local-Time Semantics

Every publication shall resolve to exactly one valid IANA timezone.

The canonical publication `timezone` shall equal the timezone of the owning Facility at acceptance.
The publisher may provide that value for explicit contract validation, but shall not assign an
arbitrary timezone. A mismatch with the Facility shall reject the complete publication.

All weekday and hour values are interpreted in this timezone. Persisted absolute timestamps remain
UTC and shall use an explicit offset in API input.

The 168 buckets represent recurring local-clock labels, not 168 elapsed UTC hours. Daylight-saving
transitions are handled as follows:

- a skipped local hour during a spring transition still has one recurring bucket, but that calendar
  occurrence contributes no observed interval to later evaluation;
- a repeated local hour during a fall transition maps both occurrences to the same recurring bucket;
- observed duration and capacity for repeated occurrences shall follow SPEC-010's timezone-aware
  interval calculation rather than assuming every occurrence lasts exactly 60 elapsed minutes;
- concrete timestamp convenience input shall first resolve the instant in the owning Facility's
  IANA timezone and then select its local weekday and hour;
- requests shall not accept ambiguous local datetime strings without an offset.

Changing a Facility timezone does not mutate accepted history. A later publication shall validate
and persist the Facility timezone current at its own acceptance. Current query interpretation uses
the timezone stored in the selected publication and shall expose it in the response.

---

# 12. Occupancy, Availability and Operational Eligibility

`expected_occupancy_rate` is the only persisted model-generated value.

`expected_availability_rate` may be returned as a derived value. It expresses predicted unused
Operational Capacity under the selected occupancy target; it does not express current technical or
business availability.

Low predicted occupancy shall not make infrastructure eligible. A Facility, Station or Connector
that is closed, inactive, under maintenance, out of service, inaccessible to the actor or otherwise
unusable shall not be presented to an EVDriver as available.

Driver-facing responses shall combine the recurring prediction with current eligibility and
operational information supplied by owning modules. They shall state that:

- the basis is a recurring weekly pattern;
- current status was applied at query time;
- no Reservation was created; and
- availability is not guaranteed.

---

# 13. Publication Aggregate

`WeeklyOccupancyPredictionPublication` shall contain at least:

- `id` — immutable publication identifier;
- `prediction_type` — `WEEKLY_OCCUPANCY`;
- `cycle` — `WEEKLY`;
- `granularity` — `HOUR`;
- `scope_type`;
- `facility_id`;
- optional `station_id` and `connector_id` according to scope;
- `timezone`;
- `contract_version` — Version 1 uses `1.0`;
- `model_name`;
- `model_version`;
- `external_run_id`;
- `generated_at`;
- `accepted_at`;
- stable authenticated `publisher_subject_id`;
- optional `dataset_export_id`;
- optional `training_data_from` and `training_data_to`;
- canonical content SHA-256 digest;
- exactly 168 Prediction Buckets.

`generated_at`, `training_data_from` and `training_data_to` are instants with explicit offsets and
shall be normalized to UTC for persistence. When either training-data boundary is provided, both
are required and shall satisfy `training_data_from < training_data_to`.

The publisher identity shall be derived from the authenticated subject. A client-supplied
publisher identifier shall not be trusted.

SCEP is not a Model Registry. A publication shall not store:

- model binaries or checkpoints;
- notebooks or source code;
- complete hyperparameter sets;
- feature pipelines;
- Python environments or dependency locks;
- automatic model deployment configuration.

`model_name`, `model_version` and `external_run_id` are traceability references, not managed model
lifecycle resources.

---

# 14. Publication Validation and Atomicity

Publication acceptance shall execute in this order:

1. authenticate and authorize the publisher;
2. validate the request schema and contract version;
3. resolve and validate the complete infrastructure hierarchy and Facility timezone;
4. validate publication metadata;
5. validate all 168 bucket values and complete key coverage;
6. canonicalize content and evaluate idempotency;
7. persist metadata and all buckets;
8. serialize current-reference evaluation for the canonical scope and compare normalized
   `generated_at` instants;
9. create or update the current-publication reference only when no current publication exists or
   the accepted publication has a strictly later `generated_at`;
10. commit once.

No publication identifier, metadata row, bucket row or current reference shall remain after any
rejection or persistence failure. Metadata, all 168 buckets and the evaluated current-reference
result shall commit atomically. A valid publication that does not become current shall still commit
as immutable history in that transaction.

Validation shall not invoke model inference or reconstruct external feature engineering.

---

# 15. Immutability, History and Current Selection

Accepted publication metadata and buckets are immutable. A new external execution creates a new
publication.

Version 1 defines no `PUT` or `PATCH` operation for accepted publications and no bucket-level write
endpoint.

Each canonical Prediction Scope has at most one mutable current-publication reference. The first
accepted publication for a scope becomes current. A subsequent accepted publication becomes
current only when its normalized `generated_at` instant is strictly later than the `generated_at`
of the existing current publication for that exact scope.

An accepted publication with an earlier `generated_at` remains historical and shall not replace the
current publication. When `generated_at` is equal, the existing current publication remains
current, and the later accepted equal-time publication remains historical. This equal-time rule is
deterministic and does not use model-version lexical order, client-provided sequence numbers,
publication identifiers or `accepted_at` as a tie-break.

Concurrent acceptance for the same canonical scope shall serialize current-reference evaluation
and update. Each transaction shall compare against the current publication visible after acquiring
the scope-specific serialization control. Consequently, final current selection is independent of
commit arrival order for different `generated_at` values. For concurrent equal-time publications
when no current publication exists, the first successfully serialized acceptance becomes current;
the other accepted publications remain historical.

An identical idempotent retry returns the existing publication and shall not reorder history or
change the current reference.

Superseded publications remain visible in authorized history queries. Version 1 forbids deletion,
deactivation and retention-based removal of accepted publication metadata or buckets. A future
governance specification may define archival without rewriting history.

---

# 16. Idempotency and Canonical Content

The stable idempotency identity is:

```text
publisher_subject_id
+ external_run_id
+ scope_type
+ facility_id
+ station_id when applicable
+ connector_id when applicable
```

The database shall enforce uniqueness of this identity.

Required behavior:

- first use with valid content creates one publication and 168 buckets;
- identical retry returns the existing publication with an equivalent successful result;
- reuse with different canonical content returns `409 Conflict`;
- rejected or rolled-back attempts do not consume the identity.

Canonical comparison shall include every client-controlled semantic publication field:

- fixed prediction type, cycle and granularity;
- contract version;
- canonical scope and hierarchy identifiers;
- Facility timezone;
- model name and version;
- external run identifier;
- generated timestamp;
- optional Dataset Export provenance;
- optional training-data window;
- all 168 bucket keys and rates.

Normalization rules are:

- enums use their canonical uppercase values;
- UUIDs use lowercase hyphenated form;
- timestamps represent the same instant in canonical UTC form;
- strings shall be non-empty, Unicode NFC normalized and free of leading or trailing whitespace;
- absent optional values normalize to JSON `null`;
- buckets are sorted in canonical weekday-major, hour-minor order;
- JSON object members use a fixed documented order;
- finite numbers use a single deterministic JSON numeric representation without changing their
  mathematical value.

The implementation shall compute SHA-256 over canonical UTF-8 bytes and persist the digest. A hash
match is an optimization; exact canonical bytes or an equivalently collision-safe comparison shall
determine identical content.

---

# 17. Dataset Export Provenance

`dataset_export_id` is optional in Version 1 because an externally generated publication may use
data with provenance managed outside SCEP. Omission shall be explicit as `null` and does not permit
direct database access.

When `dataset_export_id` is supplied:

- it shall reference an existing `COMPLETED` SPEC-011 Dataset Export;
- the referenced export shall use the `RESEARCH` Export Profile;
- the publisher shall be authorized for the referenced export under the final cross-specification
  permission mapping;
- its Facility, Station and Connector filters shall be compatible with the publication scope;
- the immutable reference shall remain queryable after artifact expiration.

`ANALYTICAL_OCCUPANCY` with the `RESEARCH` profile is the appropriate Dataset Type for the first
reference occupancy experiment because it exports SPEC-010 occupancy projections. Operational
Dataset Types may be used as additional external inputs, but the target semantics remain
`effective_occupancy_rate` from `ANALYTICAL_OCCUPANCY`.

Artifact expiration under SPEC-011 affects download availability only. It shall not invalidate,
delete or detach an accepted prediction publication. The publication retains the Dataset Export
identifier and available immutable metadata; it shall not copy or reconstruct expired artifact
content.

Current SPEC-011 authorization remains unchanged. In particular, `Researcher`, `DataScientist` and
`TechnicalClient` receive no Dataset Export access merely because SPEC-012 is drafted or approved.

The Backend API shall not reconstruct external feature engineering or bypass Dataset Export
contracts.

---

# 18. Prediction Evaluation

Observed-versus-predicted evaluation is deferred from Version 1 persistence and APIs.

A future extension may compare published values with SPEC-010 `effective_occupancy_rate`, using the
same scope, timezone, operating-hours and zero-denominator rules. It shall define explicit metric
names, versions, windows and semantics before storing results.

Version 1 shall not accept opaque evaluation maps and shall not create a second Analytics engine
inside Predictions. External experiment reports remain in the AI Research Environment.

---

# 19. REST API Conventions

All endpoints require Bearer authentication and return JSON unless otherwise stated.

Canonical scope parameters are:

- `scope_type` — required;
- `facility_id` — required;
- `station_id` — required only for `STATION` and `CONNECTOR`;
- `connector_id` — required only for `CONNECTOR`.

List endpoints use `limit` and `offset`. The default and maximum `limit` are implementation
configurable and shall be documented in OpenAPI. Collection responses contain `items`, `limit`,
`offset` and `total`.

Timestamps use RFC 3339 with an explicit offset. `generated_from` is inclusive and `generated_to`
is exclusive. Invalid or inverted ranges return `400 Bad Request`.

Errors shall use the platform error envelope and include a stable machine-readable code, a safe
message and the request identifier. Validation errors may include field locations but shall not
echo the complete 168-bucket payload.

The canonical publication summary representation is:

```json
{
  "id": "8cd1044f-41ad-4aed-9989-81731bbf779a",
  "prediction_type": "WEEKLY_OCCUPANCY",
  "cycle": "WEEKLY",
  "granularity": "HOUR",
  "scope": {
    "scope_type": "CONNECTOR",
    "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
    "station_id": "f801c6b8-2117-41f5-94bf-5a7fa314fc57",
    "connector_id": "7803c357-4637-41ea-a03a-e28192535731"
  },
  "timezone": "America/Sao_Paulo",
  "contract_version": "1.0",
  "model_name": "weekly-effective-occupancy",
  "model_version": "1.0.0",
  "external_run_id": "occ-2026-08-15-001",
  "generated_at": "2026-08-15T17:30:00Z",
  "accepted_at": "2026-08-15T17:31:04Z",
  "publisher_subject_id": "c182998e-094d-4ad8-b8ee-e996f2437b79",
  "dataset_export_id": "0d80cb12-a738-4c4d-a315-2e72c7d3b5e1",
  "training_data_from": "2026-05-01T00:00:00Z",
  "training_data_to": "2026-08-01T00:00:00Z",
  "bucket_count": 168,
  "content_sha256": "a4db0b2989d37640bbd1d25f92bf0d35d9169c1a9ff0dd68840bb2fdbfc99673",
  "is_current": true,
  "links": {
    "self": "/predictions/weekly-occupancy-publications/8cd1044f-41ad-4aed-9989-81731bbf779a",
    "profile": "/predictions/weekly-occupancy-publications/8cd1044f-41ad-4aed-9989-81731bbf779a/profile"
  }
}
```

Fields hidden by authorization shall be omitted, not returned with masked placeholder values.

---

# 20. Publish a Complete Profile

```http
POST /predictions/weekly-occupancy-publications
```

Example request, with buckets abbreviated only for documentation readability:

```json
{
  "contract_version": "1.0",
  "prediction_type": "WEEKLY_OCCUPANCY",
  "scope_type": "CONNECTOR",
  "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
  "station_id": "f801c6b8-2117-41f5-94bf-5a7fa314fc57",
  "connector_id": "7803c357-4637-41ea-a03a-e28192535731",
  "timezone": "America/Sao_Paulo",
  "model_name": "weekly-effective-occupancy",
  "model_version": "1.0.0",
  "external_run_id": "occ-2026-08-15-001",
  "generated_at": "2026-08-15T17:30:00Z",
  "dataset_export_id": "0d80cb12-a738-4c4d-a315-2e72c7d3b5e1",
  "training_data_from": "2026-05-01T00:00:00Z",
  "training_data_to": "2026-08-01T00:00:00Z",
  "buckets": [
    {
      "day_of_week": "MONDAY",
      "hour_of_day": 0,
      "expected_occupancy_rate": 0.08
    },
    {
      "day_of_week": "MONDAY",
      "hour_of_day": 1,
      "expected_occupancy_rate": 0.05
    }
  ]
}
```

The real request shall contain all 168 buckets. Abbreviated payloads shall be rejected.

New acceptance returns:

```http
201 Created
Location: /predictions/weekly-occupancy-publications/8cd1044f-41ad-4aed-9989-81731bbf779a
```

An identical idempotent retry returns `200 OK` with the existing resource and its original
`accepted_at`. Both responses include `idempotent_replay`, set to `false` or `true` respectively.

The response shall return publication metadata, canonical scope, `bucket_count = 168`,
`content_sha256`, `is_current` and links. It need not repeat all buckets; the profile resource is the
canonical full-content read.

For a new `201 Created` response, `is_current` is `true` only when the atomic selection rule in
Section 15 created or updated the scope's current reference. A valid stale or equal-time publication
returns `is_current = false` while remaining accepted and queryable. An idempotent retry reports the
existing publication's current status at retry time and never changes that status.

---

# 21. Retrieve One Publication

```http
GET /predictions/weekly-occupancy-publications/{publication_id}
```

Returns publication metadata, provenance, scope, current/superseded state and links. Technical
metadata visibility is authorization-dependent.

This resource does not include all buckets by default.

---

# 22. Retrieve a Full Profile

```http
GET /predictions/weekly-occupancy-publications/{publication_id}/profile
```

Returns publication metadata and exactly 168 canonically ordered buckets. The profile is never
paginated.

Example response fragment:

```json
{
  "publication_id": "8cd1044f-41ad-4aed-9989-81731bbf779a",
  "prediction_type": "WEEKLY_OCCUPANCY",
  "scope": {
    "scope_type": "CONNECTOR",
    "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
    "station_id": "f801c6b8-2117-41f5-94bf-5a7fa314fc57",
    "connector_id": "7803c357-4637-41ea-a03a-e28192535731"
  },
  "timezone": "America/Sao_Paulo",
  "basis": "RECURRING_WEEKLY_PATTERN",
  "bucket_count": 168,
  "buckets": [
    {
      "day_of_week": "MONDAY",
      "hour_of_day": 0,
      "expected_occupancy_rate": 0.08,
      "expected_availability_rate": 0.92
    }
  ]
}
```

---

# 23. List Publication History

```http
GET /predictions/weekly-occupancy-publications
```

Supported filters are:

| Parameter | Required | Description |
|---|---:|---|
| `scope_type` | No | `FACILITY`, `STATION` or `CONNECTOR`. |
| `facility_id` | No | Restricts history to one Facility hierarchy. |
| `station_id` | No | Requires a compatible `facility_id`. |
| `connector_id` | No | Requires compatible Facility and Station identifiers. |
| `model_name` | No | Exact canonical model-name match. |
| `model_version` | No | Exact canonical model-version match. |
| `generated_from` | No | Inclusive generation instant. |
| `generated_to` | No | Exclusive generation instant. |
| `is_current` | No | Restricts to current or superseded publications. |
| `limit` | No | Page size. |
| `offset` | No | Page offset. |

Items shall be ordered by `accepted_at` descending and `id` ascending as a deterministic tie-break.
The response includes only resources visible to the actor and returns summaries without buckets.

---

# 24. Retrieve the Current Publication

```http
GET /predictions/weekly-occupancy-publications/current
```

The request requires the complete canonical scope query. It returns current publication metadata
and links. Query parameter `include_profile=true` may include the complete ordered 168-bucket
profile; the default is `false`.

If the scope exists but has no current publication, the endpoint returns `404 Not Found` with code
`PREDICTION_CURRENT_NOT_FOUND`.

---

# 25. Point Lookup

```http
GET /predictions/weekly-occupancy/point
```

Required inputs are the complete canonical scope and either:

- `day_of_week` plus `hour_of_day`; or
- `timestamp` with an explicit offset.

The two input forms are mutually exclusive. For `timestamp`, the API selects the current
publication, resolves the instant in that publication's Facility timezone and derives the canonical
weekday/hour pair.

The response includes:

- canonical scope;
- resolved weekday, hour and timezone;
- `expected_occupancy_rate`;
- derived `expected_availability_rate`;
- publication identifier and acceptance timestamp when the actor may inspect them;
- `basis = RECURRING_WEEKLY_PATTERN`;
- `availability_guaranteed = false`.

Example:

```json
{
  "scope": {
    "scope_type": "CONNECTOR",
    "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
    "station_id": "f801c6b8-2117-41f5-94bf-5a7fa314fc57",
    "connector_id": "7803c357-4637-41ea-a03a-e28192535731"
  },
  "day_of_week": "TUESDAY",
  "hour_of_day": 18,
  "timezone": "America/Sao_Paulo",
  "expected_occupancy_rate": 0.72,
  "expected_availability_rate": 0.28,
  "basis": "RECURRING_WEEKLY_PATTERN",
  "availability_guaranteed": false
}
```

An EVDriver may use this endpoint only for infrastructure that the owning authorization and
eligibility contracts permit that driver to use. EVDriver responses omit model, Dataset Export,
publisher and external-run metadata.

---

# 26. EVDriver Connector Recommendation

## 26.1 Connectors at One Station

```http
GET /predictions/weekly-occupancy/recommendations/stations/{station_id}/connectors
```

The request requires either canonical weekday/hour input or one explicit-offset `timestamp`.

All candidates necessarily belong to the Station's single owning Facility. The endpoint shall
resolve the input using that Facility's IANA timezone. It may therefore expose one shared top-level
resolved weekday, hour and timezone, but only because the complete candidate set belongs to that
same Facility. Ranking and result items shall not imply that this shared-time response shape applies
to the cross-Facility endpoint.

## 26.2 Eligible Connectors Across Infrastructure

```http
GET /predictions/weekly-occupancy/recommendations/connectors
```

Optional `facility_id` and `station_id` filters narrow the actor's eligible infrastructure. The
complete Facility and Station hierarchy shall be validated when both are supplied.

The broad endpoint shall retain cross-Facility comparison. It shall not require all candidate
Facilities to share one timezone and shall not restrict the request to one Facility.

The two supported time-input forms have these semantics:

- for one `timestamp` with an explicit offset, the value is one absolute instant. The endpoint shall
  resolve that instant independently in every candidate Facility's IANA timezone and select each
  candidate's recurring local weekday/hour bucket independently;
- for `day_of_week` plus `hour_of_day`, the pair is local civil time interpreted independently in
  every candidate Facility's IANA timezone. Candidates in different timezones may therefore refer
  to different absolute instants when the recurring pattern is applied to a concrete week.

In both forms, each returned item shall include its Facility timezone and resolved local
`day_of_week` and `hour_of_day`. A response that may contain multiple Facilities shall not expose a
single top-level resolved timezone, weekday or hour. Top-level request information shall contain
only values valid for the complete result set, such as the original input form, recurring-pattern
basis, pagination and no-guarantee indicators.

Both endpoints accept `limit` and `offset` and return Connector candidates. Charging occurs at a
Connector, so broad Facility and Station recommendations are represented by eligible Connectors
with their owning Facility and Station included. Facility- or Station-scope publications shall not
be substituted for a missing Connector publication in Version 1.

Candidate processing shall:

1. resolve infrastructure visible and eligible for the authenticated EVDriver using owning-domain
   contracts;
2. exclude closed or operationally unavailable Facilities, Stations and Connectors;
3. resolve the request independently in each candidate Facility timezone and select that
   candidate's local recurring weekday/hour bucket;
4. require a current Connector-scope publication for the candidate's resolved local bucket;
5. derive expected availability from persisted expected occupancy;
6. order expected availability descending;
7. break ties by `facility_id`, then `station_id`, then `connector_id`, each ascending by canonical
   UUID string.

The ranking response shall include operational status needed to explain current eligibility, the
recurring pattern basis, resolved local time, rates and hierarchy identifiers. It shall not expose
model, publisher, Dataset Export, training-window or external-run details.

No result creates or holds a Reservation. A top-ranked Connector may become unavailable immediately
after the query.

Example response:

```json
{
  "request_time": {
    "input_type": "TIMESTAMP",
    "timestamp": "2026-08-04T21:00:00Z"
  },
  "basis": "RECURRING_WEEKLY_PATTERN",
  "availability_guaranteed": false,
  "reservation_created": false,
  "items": [
    {
      "rank": 1,
      "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
      "station_id": "f801c6b8-2117-41f5-94bf-5a7fa314fc57",
      "connector_id": "7803c357-4637-41ea-a03a-e28192535731",
      "resolved_time": {
        "day_of_week": "TUESDAY",
        "hour_of_day": 18,
        "timezone": "America/Sao_Paulo"
      },
      "facility_status": "Active",
      "station_status": "Active",
      "connector_status": "Available",
      "expected_occupancy_rate": 0.18,
      "expected_availability_rate": 0.82
    },
    {
      "rank": 2,
      "facility_id": "429f68cc-4ccd-4e0e-a167-3c49f143e56e",
      "station_id": "eab7b49d-83b9-42a8-9165-608bb07798da",
      "connector_id": "d624af58-5fcf-4db0-9651-579ff013d36d",
      "resolved_time": {
        "day_of_week": "TUESDAY",
        "hour_of_day": 14,
        "timezone": "America/Los_Angeles"
      },
      "facility_status": "Active",
      "station_status": "Active",
      "connector_status": "Available",
      "expected_occupancy_rate": 0.25,
      "expected_availability_rate": 0.75
    }
  ],
  "limit": 50,
  "offset": 0,
  "total": 2
}
```

This example uses one absolute instant. It selects Tuesday at 18:00 in `America/Sao_Paulo` and
Tuesday at 14:00 in `America/Los_Angeles`. For weekday/hour input, each item would retain the
requested local pair while exposing its own Facility timezone; the corresponding absolute instants
may differ.

The current approved domain does not define the EVDriver-to-Facility eligibility relationship
needed by the broad recommendation contract. That relationship is a prerequisite owned outside
Predictions. SPEC-012 shall not invent or persist it.

---

# 27. HTTP Status and Error Contract

| Status | Meaning |
|---|---|
| `200 OK` | Read succeeded or an identical publication retry returned the existing resource. |
| `201 Created` | A new complete publication was accepted atomically. |
| `400 Bad Request` | Semantic range, hierarchy, timezone, period or mutually exclusive parameter validation failed. |
| `401 Unauthorized` | Authentication is missing or invalid. |
| `403 Forbidden` | The actor, publisher or infrastructure scope is not authorized. |
| `404 Not Found` | Publication, current publication or requested infrastructure does not exist or is not visible. |
| `409 Conflict` | An idempotency identity was reused with different canonical content. |
| `422 Unprocessable Entity` | Schema, enum, contract version, bucket count or bucket completeness is invalid. |
| `500 Internal Server Error` | Atomic persistence failed without exposing internal details. |

Stable error codes shall include at least:

- `PREDICTION_BUCKET_COUNT_INVALID`;
- `PREDICTION_BUCKET_MISSING`;
- `PREDICTION_BUCKET_DUPLICATE`;
- `PREDICTION_RATE_INVALID`;
- `PREDICTION_SCOPE_INVALID`;
- `PREDICTION_HIERARCHY_MISMATCH`;
- `PREDICTION_TIMEZONE_MISMATCH`;
- `PREDICTION_IDEMPOTENCY_CONFLICT`;
- `PREDICTION_CURRENT_NOT_FOUND`;
- `PREDICTION_SCOPE_INELIGIBLE`.

Example error:

```json
{
  "code": "PREDICTION_BUCKET_MISSING",
  "message": "The weekly profile is incomplete.",
  "request_id": "8d67221b-f2b0-4ec7-bc53-d603926436a2",
  "details": [
    {
      "field": "buckets",
      "reason": "missing_weekday_hour_pair"
    }
  ]
}
```

Authorization-sensitive lookups may use `404 Not Found` instead of revealing a resource outside the
actor's visible scope, consistent with platform policy.

---

# 28. Authorization and Identity Debt

SPEC-012 introduces no Role, account type, credential type or runtime permission by itself. Final
enforcement shall reuse SPEC-005 after the cross-specification identity decision is approved.

Expected business direction is:

## 28.1 PlatformAdministrator

May inspect all scopes, publication history, full profiles, provenance and technical metadata.

## 28.2 FacilityOperator

May query current and historical predictions only for assigned Facilities and their Stations and
Connectors. Assignment shall be enforced from SPEC-005, independent of request filters. Facility
Operators shall not publish predictions unless a later explicit permission mapping grants it.

## 28.3 EVDriver

May use simplified point lookup and recommendation queries only for infrastructure eligible for
use. May not inspect publication history or internal model, dataset, run, training-window,
publisher or integrity metadata.

## 28.4 DataScientist

Is the preferred future business Role for:

- consuming anonymized `RESEARCH`-profile Dataset Exports;
- publishing prediction buckets; and
- inspecting technical prediction metadata within an authorized research scope.

These are expected future responsibilities, not current SPEC-005 or SPEC-011 permissions.

## 28.5 Researcher

Is the preferred future business Role for synthetic scenario and simulation management under
SPEC-013. SPEC-012 does not grant prediction publication merely from this Role.

## 28.6 Non-Human AI and Simulation Processes

A later cross-specification decision shall separate business Roles from credential or account
types, define least-privilege scopes, responsible Human ownership, rotation, expiration and audit,
and decide the future of `TechnicalClient`.

[GitHub issue #46](https://github.com/henricsoares/scep/issues/46) tracks this debt for SPEC-005,
SPEC-011, SPEC-012 and SPEC-013.

The debt does not block documentation approval. It shall be resolved before SPEC-012 implementation
and final runtime permission mapping. SPEC-012 shall not permanently hard-code `TechnicalClient` as
the prediction publisher and shall not redefine SPEC-005 independently.

Current SPEC-011 authorization remains unchanged until explicitly revised.

---

# 29. Persistence and Migration Requirements

The persistence design shall represent:

- immutable publication metadata;
- exactly 168 child buckets;
- canonical scope hierarchy;
- stable publisher subject;
- model and external-run references;
- Dataset Export provenance;
- training-data window;
- canonical-content digest;
- acceptance and generation timestamps;
- one current-publication reference per canonical scope;
- serialized current-reference evaluation using publication `generated_at`;
- complete history.

Critical database constraints shall include, where supported:

- primary keys for publications and buckets;
- foreign keys for Facility, Station, Connector, publisher and optional Dataset Export references;
- a scope-shape check matching Section 10;
- a timezone value validated by the application against the Facility;
- fixed prediction type, cycle, granularity and supported contract version;
- finite rate and `0 <= expected_occupancy_rate <= 1` checks;
- hour range check from `0` through `23`;
- unique `(publication_id, day_of_week, hour_of_day)`;
- unique idempotency identity from Section 16;
- unique canonical scope in the current-reference relation;
- a current-reference foreign key whose publication has the same canonical scope;
- training-data boundary completeness and ordering.

The aggregate-level count of exactly 168 buckets shall be enforced transactionally before commit;
row-level uniqueness alone is insufficient.

Required indexes shall support:

- publication lookup by identifier;
- current lookup by complete canonical scope;
- history by scope and descending generation time, with acceptance time and identifier available
  for deterministic presentation ordering;
- filtering by model name and version;
- filtering by generation period;
- Dataset Export provenance lookup;
- publisher and external-run idempotency lookup;
- bucket lookup by publication, weekday and hour.

Migrations shall be reversible and shall not modify tables owned by Facilities, Charging Stations,
Identity, Analytics or Dataset Export except through explicit foreign-key references approved at
implementation time. Downgrade shall remove only SPEC-012-owned persistence after the migration's
data-loss implications are made explicit for the operator.

---

# 30. Observability

## 30.1 Metrics

The implementation shall expose low-cardinality metrics equivalent to:

- `scep_prediction_publications_total{outcome,scope_type}`;
- `scep_prediction_idempotent_retries_total{scope_type}`;
- `scep_prediction_content_conflicts_total{scope_type}`;
- `scep_prediction_bucket_validation_failures_total{reason}`;
- `scep_prediction_publication_duration_seconds{outcome}`;
- `scep_prediction_queries_total{operation,outcome}`;
- `scep_prediction_query_duration_seconds{operation,outcome}`;
- `scep_prediction_recommendations_total{outcome}`;
- `scep_prediction_recommendation_candidates{outcome}` as a histogram or summary;
- `scep_prediction_missing_current_total{operation,scope_type}`;
- `scep_prediction_authorization_failures_total{operation}`;
- `scep_prediction_persistence_failures_total{operation}`.

Metric labels shall not contain publication, user, Facility, Station, Connector, Dataset Export or
external run identifiers. Model name and model version shall not be metric labels.

## 30.2 Structured Logs

Logs shall record request identifier, operation, outcome, scope type, bucket count, duration and
safe validation reason. Identifiers needed for investigation may appear as structured log fields
under existing access and retention controls, but secrets and Dataset Export artifact locations
shall not be logged.

Complete 168-bucket payloads shall not be logged by default. Conflict logs shall record digests or
safe metadata, not both canonical payloads.

## 30.3 Tracing

Publication traces shall cover authorization, hierarchy and timezone validation, canonicalization,
idempotency lookup, aggregate persistence and current-reference update. Query traces shall cover
authorization/eligibility resolution, current lookup, bucket lookup and ranking.

Trace attributes shall follow the same cardinality and privacy discipline as platform tracing.
Persistence failures shall be recorded without database credentials or raw SQL values.

---

# 31. OpenAPI Requirements

OpenAPI shall document:

- every path, method and operation identifier;
- Bearer authentication and Role-dependent visibility;
- all request, response, list and error schemas;
- canonical weekday, scope, prediction type, cycle and granularity enums;
- exactly 168 request buckets through schema limits plus documented uniqueness/completeness rules;
- rate bounds and finite-number requirements;
- scope hierarchy and mutually exclusive time-input rules;
- IANA timezone and RFC 3339 timestamp semantics;
- per-candidate local-time resolution for cross-Facility recommendations and the absence of a
  misleading shared timezone in those responses;
- pagination defaults and maximums;
- all status codes from Section 27;
- idempotent replay and conflict behavior;
- recurring-pattern and no-guarantee semantics;
- fields hidden from EVDriver responses.

Examples shall contain either a valid complete profile or be explicitly marked as abbreviated and
invalid for direct submission.

---

# 32. Testing Requirements

## 32.1 Domain and Contract Tests

Tests shall cover:

- exactly 168 unique buckets;
- every missing and duplicate weekday/hour combination;
- invalid, non-finite and out-of-range rates;
- invalid weekdays and hours;
- canonical deterministic ordering;
- all valid and invalid scope shapes;
- Facility, Station and Connector hierarchy mismatch;
- Facility timezone inheritance and mismatch;
- immutable accepted publications;
- no partial update contract.

## 32.2 Timezone Tests

Tests shall cover:

- local weekday/hour interpretation;
- concrete timestamp mapping;
- explicit-offset validation;
- spring skipped hours;
- fall repeated hours;
- Facility timezone changes after historical acceptance;
- one absolute timestamp resolved independently across candidate Facility timezones;
- weekday/hour input interpreted as local civil time independently across candidate Facility
  timezones;
- cross-Facility recommendation items containing their own resolved local weekday, hour and
  timezone;
- Station-specific recommendations using one shared resolved time only for candidates in the same
  owning Facility;
- zero Operational Capacity and evaluation exclusion semantics.

## 32.3 Publication and Persistence Tests

Tests shall cover:

- atomic metadata, bucket and current-reference commit;
- rollback after validation and persistence failures;
- identical idempotent retry;
- conflicting idempotency reuse;
- exactly-once persistence of all 168 buckets;
- later-`generated_at` publication replacing current atomically;
- earlier-`generated_at` publication remaining accepted historical state;
- equal-`generated_at` publication preserving the existing current reference;
- identical idempotent retry leaving current selection unchanged;
- concurrent current-publication selection serialized per canonical scope;
- concurrent different-time publications selecting the greatest `generated_at` independent of
  commit arrival order;
- concurrent equal-time publications preserving the first successfully serialized current
  publication;
- immutable history and superseded visibility;
- critical check, unique and foreign-key constraints;
- index-supported current, history and point lookups;
- migration upgrade and downgrade.

## 32.4 Authorization Tests

Tests shall cover:

- authorized prediction publisher acceptance under the final permission mapping;
- `PlatformAdministrator` visibility;
- `FacilityOperator` assigned-Facility scope;
- denial outside assigned Facilities;
- EVDriver eligible and ineligible infrastructure;
- omission of technical metadata from EVDriver responses;
- current SPEC-011 authorization remaining unchanged;
- inactive-account and invalid-credential denial.

## 32.5 Query and Recommendation Tests

Tests shall cover:

- administrative list filters, pagination and ordering;
- publication and full-profile retrieval;
- current lookup and missing-current behavior;
- point lookup by weekday/hour and timestamp;
- exclusion of closed, inactive, under-maintenance and out-of-service infrastructure;
- expected availability derivation;
- descending ranking and deterministic tie-breaking;
- timestamp-based cross-Facility ranking using independently resolved local buckets;
- weekday/hour cross-Facility ranking using independently interpreted local civil time;
- absence of one top-level resolved timezone from broad multi-Facility responses;
- item-level Facility timezone and resolved weekday/hour fields;
- Station-specific shared-time response restricted to one owning Facility;
- missing Connector publication exclusion;
- no automatic Reservation creation;
- recurring-pattern and no-guarantee response fields.

## 32.6 Cross-Specification, API and Observability Tests

Tests shall cover:

- exact compatibility with SPEC-010 `effective_occupancy_rate`;
- `ANALYTICAL_OCCUPANCY` and `RESEARCH` provenance validation from SPEC-011;
- provenance retention after artifact expiration;
- no direct PostgreSQL or external feature reconstruction path;
- all documented REST and OpenAPI contracts;
- metrics for accepted and rejected publication, retry, conflict, query and recommendation outcomes;
- structured log redaction and absence of complete bucket payloads;
- trace coverage for success, authorization and persistence failure paths;
- absence of forbidden high-cardinality metric labels.

---

# 33. Acceptance Criteria

SPEC-012 Version 1 is ready for approval when:

- one publication represents exactly one scope and exactly 168 unique buckets;
- `expected_occupancy_rate` unambiguously predicts SPEC-010 `effective_occupancy_rate`;
- weekday, hour, timezone, hierarchy, ordering and rate semantics are explicit;
- publication is immutable, atomic and safe to retry;
- identical retry and conflicting reuse behavior are deterministic;
- current selection and historical visibility are explicit;
- only a strictly later `generated_at` replaces the current publication, while earlier and equal
  timestamps remain accepted history;
- cross-Facility recommendations resolve time independently per Facility and expose resolved local
  time per item without a misleading shared timezone;
- Dataset Export provenance and expiration behavior are explicit;
- administrative, point and recommendation APIs are fully defined;
- eligibility and operational availability remain owned by existing domains;
- identity debt is recorded without changing current runtime permissions;
- Backend API training and inference are prohibited;
- persistence, migration, OpenAPI, observability and testing contracts are testable;
- SPEC-013 is documented as a recommended implementation predecessor, not a runtime dependency;
- no implementation is represented as complete.

---

# 34. Architectural Alignment

This specification is consistent with:

- SPEC-002, by reusing approved domain and Role terminology;
- SPEC-003, by treating Facility as the hierarchy and timezone root;
- SPEC-004, by preserving Station and Connector ownership and operational status;
- SPEC-005, by introducing no independent runtime Role or account-type change;
- SPEC-010, by predicting `effective_occupancy_rate` and reusing its aggregation semantics;
- SPEC-011, by using optional completed `RESEARCH` Dataset Export provenance without changing its
  current authorization;
- SPEC-013 planning, by deferring reference validation until representative synthetic data exists;
- ADR-008, by keeping feature engineering, training, evaluation and inference in the external AI
  Research Environment and accepting results only through a public authorized contract.

No approved architectural decision is overridden by this specification.

---

# End of Specification
