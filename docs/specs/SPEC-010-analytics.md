# SPEC-010 — Analytics

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

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

**Enables:**

- SPEC-011 — Dataset Export
- SPEC-012 — Predictions

---

# 1. Purpose

This specification defines the Analytics capability of the Smart Charging Experimentation Platform (SCEP).

Analytics provides deterministic, aggregated and historical views over persisted platform data. Its purpose is to transform operational records into Key Performance Indicators (KPIs) that support infrastructure analysis, capacity planning and evaluation of reservation behavior.

This specification defines:

- the Analytics module;
- analytical terminology;
- time-window and timezone rules;
- operational capacity;
- reservation behavior metrics;
- charging session metrics;
- occupancy metrics;
- energy metrics;
- analytical filtering;
- read-only REST APIs;
- authorization;
- OpenAPI;
- observability;
- acceptance and testing requirements.

Version 1 focuses on the Smart Charging domain while preserving a domain-independent Analytics
architecture.

---

# 2. Goals

This specification shall:

- provide historical and aggregated views over persisted business data;
- expose deterministic KPIs;
- distinguish reserved capacity from effective charging usage;
- measure whether Reservations result in Charging Sessions;
- quantify cancellations, late cancellations and No-Shows;
- measure utilization of reserved time;
- aggregate Charging Session duration and delivered energy;
- use Facility operating hours as the reference for operational capacity;
- provide consistent filters across analytical endpoints;
- reuse the existing authorization model;
- remain extensible for future business domains;
- support future Dataset Export and Predictions specifications.

---

# 3. Scope

This specification includes:

- read-only analytical queries;
- on-demand metric computation;
- Smart Charging analytical projections;
- Reservation metrics;
- Charging Session metrics;
- capacity and occupancy metrics;
- energy metrics;
- time-series aggregation;
- Facility, Charging Station and Connector filtering;
- timezone-aware grouping;
- REST API contracts;
- authorization;
- OpenAPI;
- observability;
- acceptance criteria;
- testing requirements.

---

## Out of Scope

The following capabilities are intentionally deferred:

- graphical dashboards;
- frontend visualization;
- Business Intelligence tools;
- real-time monitoring;
- streaming analytics;
- materialized views;
- analytical caches;
- analytical data warehouses;
- scheduled reports;
- dataset export;
- predictive analytics;
- machine learning models;
- recommendation systems;
- anomaly or fraud detection;
- user rankings;
- behavioral scoring;
- billing;
- pricing;
- penalties;
- notifications;
- Digital Twin execution.

The Digital Twin Simulation Engine defined by SPEC-013 shall generate synthetic operational
activity independently from Analytics. Analytics may evaluate that activity only after it has been
persisted through the normal operational domain.

---

# 4. Relationship with Existing Domains

Analytics consumes persisted data owned by existing platform domains.

It does not own or modify:

- Facilities;
- Charging Stations;
- Connectors;
- Reservations;
- Charging Sessions;
- TelemetrySamples;
- Domain Events.

The initial analytical sources are:

```text
Facility
    │
    └── operating hours and timezone
            │
            ▼
Charging Station
    │
    ▼
Connector
    │
    ├──────────────► Reservation
    │                    │
    │                    ▼
    └──────────────► Charging Session
                         │
                         ▼
                   TelemetrySample
                         │
                         ▼
                      Analytics
```

Version 1 shall compute metrics directly from persisted operational entities using on-demand queries.

Although SPEC-009 is implemented, Domain Events are not required as the source of Analytics metrics
in version 1. A future version may use event-driven projections without changing the public metric
definitions or REST contracts defined here.

Analytics shall never change operational state.

---

# 5. Analytics Architecture

Analytics is a cross-cutting platform capability.

The module shall expose domain-specific analytical projections through a shared application and API layer.

```text
                       REST API
                           │
                           ▼
                  Analytics Application
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
       Reservations     Occupancy      Energy
        Projection      Projection    Projection
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                 Operational Database
```

The initial implementation shall:

- query the operational PostgreSQL database;
- compute metrics on demand;
- remain stateless between requests;
- return read-only analytical responses;
- avoid duplicating operational business rules;
- avoid introducing a separate analytical persistence model.

Future domains may contribute additional analytical projections without changing the overall Analytics architecture.

---

# 6. Ubiquitous Language

## Analysis Window

The half-open time interval `[from, to)` evaluated by an analytical query.

`from` is inclusive.

`to` is exclusive.

## Analytical Scope

The set of Facilities, Charging Stations or Connectors included after authorization and request filters are applied.

## Time Bucket

One timezone-aware subdivision of the Analysis Window.

Supported granularities are:

```text
hour
day
week
month
```

## Operational Capacity

The total Connector time available during Facility operating hours inside the Analysis Window.

Operational Capacity is measured as time multiplied by the number of in-scope Connectors.

## Available Duration

Operational Capacity expressed as duration.

For Facility-level queries, one hour of operation with four in-scope Connectors produces four connector-hours of Available Duration.

## Reserved Duration

The sum of Reservation interval portions that intersect the Analysis Window and the corresponding Facility operating hours.

## Charging Duration

The sum of Charging Session interval portions that intersect the Analysis Window and the corresponding Facility operating hours.

## Fulfilled Reservation

A Reservation that resulted in exactly one Charging Session.

## Eligible Reservation

A Reservation whose attendance outcome is known.

Eligible Reservations are:

- Fulfilled Reservations;
- No-Show Reservations.

Cancelled and Late Cancelled Reservations are reported separately and are not eligible for the Reservation Fulfillment Rate.

## Effective Reserved Charging Duration

The portion of Charging Duration that overlaps the Reservation interval associated with the Charging Session.

This concept measures how much reserved time was effectively used.

## Delivered Energy

The energy delivered during a Charging Session, derived from persisted `energy_kwh` telemetry.

Because `energy_kwh` is an accumulated measurement, delivered energy for one session is determined
from the maximum valid persisted accumulated value observed for that session inside the Analysis
Window. Version 1 does not subtract, interpolate or otherwise infer values at window boundaries.

Missing energy telemetry shall remain unknown and shall not be interpreted as zero.

---

# 7. Time Model

All persisted timestamps shall remain in UTC.

Analytical queries may specify a target IANA timezone for grouping and presentation.

When exactly one Facility is in scope and no timezone is provided, the Facility timezone shall be used.

When multiple Facilities are in scope, the request shall provide an explicit timezone. A Platform Administrator query without a Facility filter shall therefore require `timezone`.

All Analysis Windows shall use the half-open interval convention:

```text
[from, to)
```

Time buckets shall be created in the requested timezone and converted to UTC only for data selection.

Timezone grouping shall respect daylight-saving transitions defined by the IANA timezone database.

The implementation shall not use a hidden server-local timezone.

The same persisted state and the same query parameters shall produce the same result.

---

# 8. Operational Capacity Model

Operational Capacity shall be derived from Facility operating hours.

For one Connector:

```text
Available Duration
=
Facility Operating Hours intersected with Analysis Window
```

For multiple Connectors:

```text
Available Duration
=
sum of operating duration for every in-scope Connector
```

If a Facility does not define `operating_hours`, it shall be treated as continuously operational during the Analysis Window.

Facility operating hours represent 100% of theoretical operational capacity.

Version 1 shall not reduce Available Duration because of:

- Connector faults;
- Connector status changes;
- Facility maintenance;
- infrastructure outages;
- missing telemetry;
- application downtime.

Historical technical availability is not available as a time series in the current domain model. A future specification may introduce Effective Available Duration after historical infrastructure status becomes available.

Facility operating hours shall be evaluated using the Facility timezone.

Intervals outside Facility operating hours shall not contribute to:

- Available Duration;
- Reserved Duration;
- Charging Duration;
- occupancy rates;
- reserved-time utilization.

---

# 9. Analytical Selection Rules

## Reservation Selection

Count-based Reservation metrics shall select Reservations whose scheduled `start_at` belongs to the Analysis Window.

Duration-based Reservation metrics shall use the intersection among:

- the Reservation interval;
- the Analysis Window;
- Facility operating hours.

The current persisted Reservation status shall determine cancellation and No-Show classifications.

A Reservation shall be considered fulfilled when a Charging Session references its identifier, regardless of whether the session is currently ACTIVE or COMPLETED.

## Charging Session Selection

Count-based Charging Session metrics shall select sessions whose `started_at` belongs to the Analysis Window.

Duration-based Charging Session metrics shall include every session that overlaps the Analysis Window.

For a COMPLETED Charging Session, the effective session interval is:

```text
[started_at, ended_at)
```

For an ACTIVE Charging Session, the effective end shall be the earlier value between:

- the query processing timestamp;
- `to`.

The query processing timestamp shall be captured once at the start of the request and reused for all calculations.

Public Analytics REST endpoints shall continue to use their request processing timestamp. An
internal read-only projection consumer may supply an explicit processing timestamp while preserving
the same metric formulas. Dataset Export shall supply its `data_cutoff_at` so every exported bucket
uses one processing boundary. This internal contract does not change the public Analytics REST API.

## Telemetry Selection

Telemetry shall be associated with Analytics through Charging Session ownership.

Energy calculations shall include only persisted, valid `energy_kwh` values.

For each session, the delivered energy value shall be the maximum accumulated `energy_kwh` value whose `recorded_at` belongs to the Analysis Window.

A session without energy telemetry shall:

- remain included in session counts and duration metrics;
- be excluded from energy averages;
- increment the missing-energy session count.

Telemetry values shall never be inferred from power measurements, interpolation or missing samples
in version 1.

## Interval Clipping

All duration metrics shall clip source intervals to both:

- the Analysis Window;
- Facility operating hours.

Back-to-back intervals shall not overlap because all intervals are half-open.

---

# 10. Metric Definitions

All rates shall be returned as decimal values between `0` and `1`.

Percent formatting belongs to clients and is outside the API contract.

When a denominator is zero, the corresponding rate shall be `null`.

Durations shall be returned in minutes as decimal values.

Energy shall be returned in kilowatt-hours.

## Reservation Metrics

### total_reservations

Number of Reservations whose scheduled `start_at` belongs to the Analysis Window.

### fulfilled_reservations

Number of selected Reservations that resulted in a Charging Session.

### cancelled_reservations

Number of selected Reservations with status `CANCELLED`.

### late_cancelled_reservations

Number of selected Reservations with status `LATE_CANCELLED`.

### no_show_reservations

Number of selected Reservations with status `NO_SHOW`.

### pending_reservations

Number of selected Reservations that do not yet have a final attendance outcome.

This includes selected Reservations that remain `CONFIRMED`.

ACTIVE Reservations are fulfilled and shall not be counted as pending.

### reservation_fulfillment_rate

```text
fulfilled_reservations
/
(fulfilled_reservations + no_show_reservations)
```

Cancelled and Late Cancelled Reservations shall not be part of this denominator.

### cancellation_rate

```text
cancelled_reservations
/
total_reservations
```

### late_cancellation_rate

```text
late_cancelled_reservations
/
total_reservations
```

### no_show_rate

```text
no_show_reservations
/
(fulfilled_reservations + no_show_reservations)
```

### average_reservation_duration_minutes

Average clipped Reserved Duration per Reservation that contributes positive Reserved Duration.

## Capacity and Occupancy Metrics

### available_duration_minutes

Total Operational Capacity of the analytical scope within the Analysis Window.

### reserved_duration_minutes

Total clipped Reserved Duration.

Reservations with the following statuses shall contribute to Reserved Duration:

```text
CONFIRMED
ACTIVE
COMPLETED
NO_SHOW
```

Cancelled and Late Cancelled Reservations shall not contribute to Reserved Duration in version 1.

### charging_duration_minutes

Total clipped Charging Duration.

### reserved_occupancy_rate

Reserved Occupancy measures scheduled capacity commitment.

```text
reserved_duration_minutes
/
available_duration_minutes
```

### effective_occupancy_rate

Effective Occupancy measures actual Charging Session usage.

```text
charging_duration_minutes
/
available_duration_minutes
```

### effective_reserved_charging_duration_minutes

Total overlap among:

- Charging Session interval;
- associated Reservation interval;
- Analysis Window;
- Facility operating hours.

### reserved_time_utilization_rate

```text
effective_reserved_charging_duration_minutes
/
reserved_duration_minutes
```

Charging time outside the associated Reservation interval shall not increase this rate.

### unused_reserved_duration_minutes

```text
reserved_duration_minutes
-
effective_reserved_charging_duration_minutes
```

The result shall never be negative.

## Charging Session Metrics

### total_charging_sessions

Number of Charging Sessions whose `started_at` belongs to the Analysis Window.

### active_charging_sessions

Number of selected Charging Sessions with status `ACTIVE`.

### completed_charging_sessions

Number of selected Charging Sessions with status `COMPLETED`.

### average_session_duration_minutes

Average clipped Charging Duration per session that contributes positive Charging Duration.

### average_session_start_delay_minutes

Average difference between `ChargingSession.started_at` and the associated `Reservation.start_at`.

Negative values represent Early Start.

Only sessions whose `started_at` belongs to the Analysis Window shall contribute.

### on_time_start_rate

Ratio of selected Charging Sessions started inside the Reservation activation window defined by SPEC-006:

```text
Reservation.start_at - 15 minutes
through
Reservation.start_at + 15 minutes
```

Both boundaries are inclusive for this classification.

The denominator is `total_charging_sessions`.

## Energy Metrics

### total_delivered_energy_kwh

Sum of session Delivered Energy values.

Sessions without valid energy telemetry shall not contribute zero.

This metric reports accumulated values actually persisted inside the Analysis Window; it does not
infer energy delivered before the first or after the last included sample.

### sessions_with_energy_data

Number of selected sessions with at least one valid accumulated `energy_kwh` value in the Analysis Window.

### sessions_without_energy_data

Number of selected sessions without a valid accumulated `energy_kwh` value in the Analysis Window.

### average_energy_per_session_kwh

```text
total_delivered_energy_kwh
/
sessions_with_energy_data
```

When `sessions_with_energy_data` is zero, the result shall be `null`.

---

# 11. Time-Series Aggregation

Endpoints that support `granularity` shall return one ordered result per Time Bucket.

Supported values are:

```text
hour
day
week
month
```

Bucket boundaries shall be evaluated in the requested timezone.

Weeks shall begin on Monday.

Months shall follow calendar-month boundaries.

Each bucket shall use the same half-open interval convention:

```text
[bucket_from, bucket_to)
```

The first and last buckets may be partial because they shall be clipped to the Analysis Window.

Duration values shall be attributed according to actual interval overlap with each bucket.

Count values shall be attributed according to the selection timestamp defined for that entity:

- Reservation counts use `Reservation.start_at`;
- Charging Session counts use `ChargingSession.started_at`;
- Telemetry observations use `TelemetrySample.recorded_at`.

The sum of bucket duration values shall equal the corresponding duration value for the complete Analysis Window, subject only to documented numeric precision.

---

# 12. Filtering

All Analytics endpoints shall use a consistent filtering model.

| Parameter | Required | Description |
|---|---:|---|
| `from` | Yes | Analysis Window start, inclusive. |
| `to` | Yes | Analysis Window end, exclusive. |
| `facility_id` | No | Restricts results to one Facility. |
| `station_id` | No | Restricts results to one Charging Station. |
| `connector_id` | No | Restricts results to one Connector. |
| `timezone` | Conditional | IANA timezone used for grouping and presentation. |
| `granularity` | Endpoint-specific | `hour`, `day`, `week` or `month`. |

Filter hierarchy shall be validated.

When more than one infrastructure filter is provided:

- the Connector shall belong to the specified Charging Station;
- the Charging Station shall belong to the specified Facility.

Mismatched filter combinations shall return `400 Bad Request`.

The Analysis Window shall satisfy `from < to`.

Both timestamps shall include an explicit timezone offset.

The maximum Analysis Window in version 1 shall be 366 days.

Requests exceeding this limit shall return `400 Bad Request`.

Pagination is not required because Analytics endpoints return aggregate results rather than entity collections.

---

# 13. REST API

The Analytics module shall expose:

```text
GET /analytics/overview
GET /analytics/reservations
GET /analytics/charging-sessions
GET /analytics/occupancy
GET /analytics/energy
```

All endpoints shall:

- require authentication;
- enforce analytical scope authorization;
- accept the common filters defined by this specification;
- return JSON;
- remain read-only;
- return deterministic results for identical persisted state and parameters.

## GET /analytics/overview

Returns a compact summary containing the principal metrics from all analytical groups.

```json
{
  "window": {
    "from": "2026-07-01T00:00:00Z",
    "to": "2026-08-01T00:00:00Z",
    "timezone": "America/Sao_Paulo"
  },
  "scope": {
    "facility_id": "9cc7dd93-c072-4860-86ca-23c224b767d3",
    "station_id": null,
    "connector_id": null
  },
  "reservations": {
    "total_reservations": 240,
    "fulfilled_reservations": 180,
    "cancelled_reservations": 20,
    "late_cancelled_reservations": 10,
    "no_show_reservations": 20,
    "pending_reservations": 10,
    "reservation_fulfillment_rate": 0.9,
    "cancellation_rate": 0.083333,
    "late_cancellation_rate": 0.041667,
    "no_show_rate": 0.1
  },
  "capacity": {
    "available_duration_minutes": 44640.0,
    "reserved_duration_minutes": 22320.0,
    "charging_duration_minutes": 16740.0,
    "effective_reserved_charging_duration_minutes": 16020.0,
    "unused_reserved_duration_minutes": 6300.0,
    "reserved_occupancy_rate": 0.5,
    "effective_occupancy_rate": 0.375,
    "reserved_time_utilization_rate": 0.717742
  },
  "charging_sessions": {
    "total_charging_sessions": 180,
    "active_charging_sessions": 4,
    "completed_charging_sessions": 176,
    "average_session_duration_minutes": 93.0,
    "average_session_start_delay_minutes": 6.4,
    "on_time_start_rate": 0.82
  },
  "energy": {
    "total_delivered_energy_kwh": 3960.5,
    "sessions_with_energy_data": 170,
    "sessions_without_energy_data": 10,
    "average_energy_per_session_kwh": 23.297059
  }
}
```

## Specialized Endpoints

`GET /analytics/reservations` shall return Reservation behavior and duration metrics.

`GET /analytics/charging-sessions` shall return Charging Session count, duration and punctuality metrics.

`GET /analytics/occupancy` shall return theoretical capacity, reserved capacity and effective usage metrics.

`GET /analytics/energy` shall return accumulated delivered-energy metrics derived from Telemetry.

When `granularity` is omitted, specialized endpoints shall return one aggregate result.

When `granularity` is provided, specialized endpoints shall also return an ordered `series`.

A Time-Series Item shall use:

```json
{
  "from": "2026-07-01T00:00:00-03:00",
  "to": "2026-07-02T00:00:00-03:00",
  "metrics": {}
}
```

## HTTP Status Codes

| Status | Meaning |
|---|---|
| `200 OK` | Analytics query completed successfully. |
| `400 Bad Request` | Invalid time window, timezone, granularity or filter hierarchy. |
| `401 Unauthorized` | Authentication is missing or invalid. |
| `403 Forbidden` | The actor cannot access the requested analytical scope. |
| `404 Not Found` | A requested Facility, Charging Station or Connector does not exist. |
| `422 Unprocessable Entity` | Request parameter schema validation failed. |

An empty analytical result shall return `200 OK` with zero counts, zero durations and `null` rates whose denominators are zero.

---

# 14. Authorization

Analytics shall reuse the authentication and authorization model defined by SPEC-005.

## Platform Administrator

A Platform Administrator may query:

- all Facilities;
- any Charging Station;
- any Connector;
- cross-Facility analytical results.

Cross-Facility queries shall require an explicit timezone.

## Facility Operator

A Facility Operator may query only analytical data belonging to Facilities within the operator's authorized scope.

The server shall enforce the Facility restriction independently from request filters.

A Facility Operator shall not obtain cross-Facility results.

## Other Actors

Human Accounts, Technical Clients, Researchers and Data Scientists shall not receive Analytics access in version 1 unless SPEC-005 already grants an equivalent explicit administrative or Facility scope.

This specification introduces no new role and no new ownership model.

Unauthorized analytical scope shall return `403 Forbidden`.

---

# 15. Query and Persistence Requirements

Version 1 shall not create analytical Aggregate tables.

Analytics queries shall use existing persisted data.

The implementation may create database indexes required for acceptable query performance.

Recommended index coverage includes:

- Reservation `start_at`;
- Reservation `connector_id`;
- Reservation `status`;
- Charging Session `started_at`;
- Charging Session `connector_id`;
- Charging Session `reservation_id`;
- TelemetrySample `session_id`;
- TelemetrySample `recorded_at`.

Analytics shall not update operational tables.

Analytics shall not persist query results.

Numeric calculations shall use database or application numeric types that avoid uncontrolled floating-point accumulation.

Returned rates and energy values shall use a documented fixed maximum precision.

The implementation shall preserve exact metric definitions regardless of whether aggregation occurs in SQL or application code.

---

# 16. Observability

Analytics shall expose operational metrics consistent with the platform observability model.

Metrics shall avoid high-cardinality labels such as Facility, Charging Station, Connector or actor identifiers.

At minimum, the implementation shall expose:

- analytical requests by endpoint;
- successful analytical requests;
- failed analytical requests;
- analytical query duration;
- returned time-bucket count.

Structured logs shall be emitted for:

- analytical query start;
- analytical query completion;
- validation failures;
- authorization failures;
- query execution failures.

Sensitive data and complete analytical responses shall not be written to logs.

---

# 17. OpenAPI

Generated OpenAPI documentation shall include:

- Analytics Window schema;
- Analytics Scope schema;
- Reservation Metrics schema;
- Charging Session Metrics schema;
- Occupancy Metrics schema;
- Energy Metrics schema;
- Time-Series Item schemas;
- common filter parameters;
- supported granularities;
- authentication requirements;
- authorization notes;
- response examples;
- error responses.

Bearer authentication shall be declared for every Analytics endpoint.

Rate fields shall be documented as nullable decimal values between `0` and `1`.

Duration fields shall be documented in minutes.

Energy fields shall be documented in kilowatt-hours.

---

# 18. Acceptance Criteria

The implementation shall satisfy the following acceptance criteria.

## Architecture

- Analytics module implemented as a read-only platform capability.
- Smart Charging analytical projections implemented.
- No operational business state is modified.
- No analytical persistence or cache is required.
- Existing operational APIs remain unaffected.

## Time Model

- UTC persistence preserved.
- IANA timezone validation implemented.
- Facility timezone used for single-Facility queries when omitted.
- Explicit timezone required for multi-Facility queries.
- Half-open Analysis Windows enforced.
- Time buckets respect timezone and daylight-saving rules.
- Maximum 366-day Analysis Window enforced.

## Capacity

- Facility operating hours define theoretical capacity.
- Missing operating hours are treated as continuous operation.
- Connector count contributes to Available Duration.
- Duration metrics are clipped to Facility operating hours.
- Infrastructure status does not reduce version 1 capacity.

## Metrics

- Reservation behavior metrics implemented.
- reserved and effective occupancy metrics implemented.
- Reserved Time Utilization implemented.
- Charging Session duration and punctuality metrics implemented.
- accumulated energy metrics implemented.
- missing energy is not treated as zero.
- zero-denominator rates return `null`.

## API

- all five Analytics endpoints implemented.
- common filters supported.
- filter hierarchy validated.
- aggregate responses implemented.
- time-series responses implemented.
- empty results return stable response schemas.
- OpenAPI generated successfully.

## Authorization

- Platform Administrator global access validated.
- Facility Operator scoped access validated.
- unauthorized Facility access denied.
- cross-Facility access denied to Facility Operators.
- no new roles introduced.

## Observability

- request counters exposed.
- query duration exposed.
- structured logs emitted.
- high-cardinality metric labels avoided.
- sensitive analytical data excluded from logs.

---

# 19. Testing Requirements

The implementation shall include automated tests covering:

## Metric Unit Tests

- Reservation count metrics;
- fulfillment-rate denominator;
- cancellation and Late Cancellation rates;
- No-Show Rate;
- zero denominators;
- Reserved and Effective Occupancy Rates;
- Reserved Time Utilization Rate;
- unused Reserved Duration;
- session duration;
- start delay;
- On-Time Start Rate;
- accumulated energy selection;
- missing energy behavior.

## Time Tests

- half-open window boundaries;
- back-to-back intervals;
- interval clipping;
- Facility timezone default;
- explicit cross-Facility timezone;
- hourly, daily, weekly and monthly grouping;
- daylight-saving transition;
- ACTIVE session query timestamp consistency;
- partial first and last buckets.

## Capacity Tests

- one Connector capacity;
- multiple Connector capacity;
- configured Facility operating hours;
- continuously operational Facility;
- Reservation outside operating hours;
- session outside operating hours;
- infrastructure status not subtracted;
- empty analytical scope.

## Integration Tests

- persisted Reservations;
- persisted Charging Sessions;
- persisted TelemetrySamples;
- Facility, Charging Station and Connector filters;
- matching and mismatched hierarchical filters;
- empty result response;
- database index migration when introduced.

## Authorization Tests

- Platform Administrator global query;
- Platform Administrator Facility query;
- Facility Operator authorized query;
- Facility Operator unauthorized query;
- Facility Operator cross-Facility denial;
- unauthenticated request;
- unsupported actor denial.

## API Tests

- overview endpoint;
- Reservations endpoint;
- Charging Sessions endpoint;
- occupancy endpoint;
- energy endpoint;
- aggregate and time-series response schemas;
- invalid timezone;
- invalid granularity;
- invalid Analysis Window;
- Analysis Window exceeding 366 days;
- OpenAPI validation.

## Docker Compose

A complete smoke test shall validate:

- automatic migrations;
- backend health;
- existing Reservation workflow;
- existing Charging Session workflow;
- existing Telemetry ingestion;
- Analytics overview;
- Analytics time-series query;
- authorization;
- OpenAPI;
- Prometheus metrics;
- existing business workflows remain unaffected.

---

# 20. Future Integration

Analytics establishes the official KPI and historical aggregation capability of SCEP.

Future specifications may extend or consume this capability through:

- Dataset Export;
- Predictions;
- additional analytical domains;
- cached projections;
- materialized views;
- analytical warehouses;
- event-driven projection updates;
- historical infrastructure availability;
- comparative reports.

SPEC-011 may export operational or analytical data, but Dataset Export remains a separate capability.

SPEC-012 may consume persisted operational data or analytical results, but prediction behavior remains outside this specification.

A future Digital Twin Simulation Engine shall generate synthetic users, vehicles, Reservations, Charging Sessions and Telemetry independently from historical Analytics data.

The relationship shall be:

```text
Digital Twin Simulation
          │
          ▼
Synthetic Operational Activity
          │
          ▼
Reservations + Charging Sessions + Telemetry
          │
          ▼
Analytics
```

Analytics evaluates persisted synthetic activity in the same way it evaluates real operational
activity. Analytics shall never be a prerequisite for Digital Twin execution.

---

# 21. Dependencies

Analytics depends on previously implemented platform capabilities.

The implementation requires:

- SPEC-003 — Facilities;
- SPEC-004 — Charging Stations;
- SPEC-005 — Identity and Access;
- SPEC-006 — Reservations;
- SPEC-007 — Charging Sessions;
- SPEC-008 — Telemetry.

This specification does not redefine concepts owned by those modules.

In particular:

- Facility timezone and operating hours remain governed by SPEC-003;
- Charging Station and Connector ownership remain governed by SPEC-004;
- authentication and authorization remain governed by SPEC-005;
- Reservation lifecycle and activation windows remain governed by SPEC-006;
- Charging Session lifecycle remains governed by SPEC-007;
- Telemetry measurement semantics remain governed by SPEC-008.

SPEC-009 remains authoritative for Domain Events, but Domain Events are not a mandatory data source
for the version 1 implementation.

Whenever an earlier specification defines operational business behavior, that specification takes precedence.

---

# 22. Implementation Notes

The implementation shall preserve the layered architecture established by the platform.

A recommended structure is:

```text
analytics/
    api/
    application/
    projections/
        smart_charging/
    infrastructure/
```

The exact file layout is implementation-defined.

Analytics projection code shall:

- depend on read interfaces rather than operational service commands;
- avoid invoking state-changing domain methods;
- centralize common filters and time-window validation;
- centralize Facility operating-hours calculations;
- reuse metric definitions across overview and specialized endpoints;
- capture the request processing timestamp once;
- accept an explicit processing timestamp from authorized internal projection consumers;
- avoid N+1 queries;
- keep SQL and application calculations behaviorally equivalent;
- preserve deterministic ordering of time-series buckets.

Version 1 intentionally favors direct, understandable queries over premature analytical infrastructure.

---

# 23. Specification Summary

This specification introduces Analytics as a read-only, cross-cutting platform capability.

The initial implementation analyzes the Smart Charging domain through persisted Reservations, Charging Sessions, Telemetry and Facility configuration.

Facility operating hours define 100% of theoretical operational capacity.

```text
Facility Operating Hours
          ×
In-Scope Connectors
          │
          ▼
Available Duration
```

Analytics distinguishes scheduled commitment from actual charging usage.

```text
Available Duration
      │
      ├────────────► Reserved Duration
      │                    │
      │                    ▼
      │          Reserved Occupancy Rate
      │
      └────────────► Charging Duration
                           │
                           ▼
                 Effective Occupancy Rate
```

Reservation behavior is evaluated by relating Reservations to their resulting Charging Sessions.

```text
Reservation
    │
    ├── Charging Session ─────► Fulfilled
    ├── NO_SHOW ──────────────► Not Fulfilled
    ├── CANCELLED ────────────► Cancelled
    └── LATE_CANCELLED ───────► Late Cancelled
```

Reserved Time Utilization measures only charging that overlaps the associated Reservation interval.

Energy metrics use accumulated `energy_kwh` telemetry. Missing energy remains unknown and is never interpreted as zero.

All analytical queries:

- are read-only;
- use half-open time windows;
- are timezone-aware;
- support consistent infrastructure filters;
- enforce existing authorization;
- return deterministic aggregate or time-series responses.

Analytics remains domain-independent. Future domains may add new projections without changing the module architecture.

Dataset Export and Predictions may consume Analytics in later specifications.

The Digital Twin remains an independent synthetic data generator:

```text
Digital Twin
      │
      ▼
Synthetic Operational Data
      │
      ▼
Analytics
```

This avoids a circular dependency and allows SCEP to generate and analyze experimental data before real-world data becomes available.

---

# End of Specification
