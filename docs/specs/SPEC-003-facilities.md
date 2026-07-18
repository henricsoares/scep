# SPEC-003 — Facilities

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

This specification defines the **Facility Aggregate**, which represents the highest-level business entity within the Smart Charging Experimentation Platform (SCEP).

A Facility provides the operational context in which charging infrastructure exists, users interact with the platform and experiments are conducted.

All Charging Stations, Connectors, Reservations and Charging Sessions ultimately belong to a
Facility. TelemetrySamples are associated with Charging Sessions within that operational context.

For this reason, the Facility Aggregate serves as the root of the Smart Charging domain.

---

# 2. Scope

This specification defines:

* the Facility Aggregate;
* Facility lifecycle;
* Facility properties;
* operational status;
* operational calendar;
* business rules;
* validation rules;
* ownership responsibilities.

This specification does **not** define:

* Charging Stations;
* Connectors;
* Reservations;
* Charging Sessions;
* Authentication.

These concerns are covered by subsequent specifications.

---

# 3. Business Motivation

Charging infrastructure does not exist in isolation.

Every charging station belongs to a real operational environment such as:

* a residential condominium;
* a shopping center;
* a university campus;
* a corporate building;
* a public parking facility.

These environments possess different usage patterns, operating schedules and occupancy profiles.

The Facility Aggregate captures this operational context.

Instead of managing isolated charging stations, SCEP manages **charging infrastructure within a Facility**.

This distinction is fundamental for simulation, analytics and Artificial Intelligence.

---

# 4. Aggregate Responsibilities

The Facility Aggregate is responsible for:

* representing a physical operational environment;
* identifying charging infrastructure ownership;
* defining operational boundaries;
* grouping charging stations;
* defining operating schedules;
* supporting occupancy analysis;
* providing the contextual unit for AI predictions.

It is **not** responsible for managing charging sessions or reservations directly.

---

# 5. Aggregate Root

Facility is the Aggregate Root.

It owns:

* Charging Stations.

Indirectly, it provides context for:

* Connectors;
* Reservations;
* Charging Sessions;
* Telemetry;
* Analytics;
* Predictions.

Business operations shall always begin from the Facility perspective.

---

# 6. Conceptual Model

```text id="qmk8xe"
Facility

    │

    ├──────── owns ────────► Charging Stations

    │

    ├──────── defines ─────► Operating Hours

    │

    ├──────── groups ──────► Charging Infrastructure

    │

    ├──────── contextualizes ─► Analytics

    │

    └──────── contextualizes ─► Predictions
```

The Facility provides organizational context rather than operational behavior.

---

# 7. Business Attributes

Every Facility shall contain the following business information.

## Identifier

Unique identifier.

Immutable.

---

## Name

Human-readable facility name.

Examples:

* Alpha Residence
* Downtown Shopping Center
* North Campus

Required.

---

## Description

Optional textual description.

Used for administrative purposes.

---

## Facility Type

Classifies the operational environment.

Supported values:

* Residential;
* Commercial;
* University;
* Industrial;
* Public Parking;
* Shopping Center;
* Corporate Campus.

Future values may be introduced without changing the Aggregate structure.

---

## Location

Represents the geographical location of the Facility.

Initially includes:

* address;
* city;
* state;
* country.

Future versions may include geographic coordinates.

---

## Time Zone

Represents the local time zone.

Required for:

* reservations;
* simulations;
* analytics;
* prediction windows.

The platform shall avoid assuming UTC for business operations.

---

## Operational Status

Represents whether the Facility is operational.

Supported values:

* Active;
* Inactive;
* Under Maintenance.

Inactive Facilities cannot receive new reservations.

---

## Operating Hours

Represents the expected period during which charging infrastructure is available.

Operating Hours are defined independently for each day of the week.

Example:

```text id="0mup7d"
Monday

08:00

22:00
```

Operating Hours are advisory in this specification.

Enforcement rules are defined in Reservation specifications.

---

# 8. Business Value

The Facility Aggregate creates value by organizing operational information.

Without Facilities:

* occupancy metrics lose context;
* simulations become unrealistic;
* AI models cannot distinguish operational environments;
* analytics cannot be segmented.

Facilities therefore become the primary analytical dimension of the platform.

---

# 9. Domain Events

The following Domain Events originate from Facility operations.

* FacilityCreated
* FacilityUpdated
* FacilityActivated
* FacilityDeactivated
* FacilityMaintenanceStarted
* FacilityMaintenanceFinished

These events support:

* observability;
* audit trails;
* operational analytics.

---

# 10. Domain Principles

The following principles govern the Facility Aggregate.

## Single Ownership

Every Charging Station belongs to exactly one Facility.

---

## Operational Context

A Facility defines the operational environment, not the charging process.

---

## Long Lifecycle

Facilities are expected to remain stable over long periods.

Most operational changes occur within Charging Stations and Connectors.

---

## Stable Identity

Changing Facility attributes does not create a new Facility.

Identity is preserved throughout its lifecycle.

---

## Analytics Boundary

Facility is the highest-level business dimension for analytics and prediction.

All KPIs produced by SCEP shall be traceable to a Facility.

---

# 11. Domain Model

The Facility Aggregate is intentionally simple.

Its responsibility is not to execute business workflows, but to establish the operational context in which those workflows occur.

Conceptually, the model is represented below.

```text
Facility

    │

    ├──────── contains ─────────────► Charging Stations

    │

    ├──────── defines ──────────────► Operating Hours

    │

    ├──────── located at ───────────► Location

    │

    ├──────── classified as ────────► Facility Type

    │

    └──────── contextualizes ───────► Infrastructure Utilization
```

The Facility Aggregate owns only information directly related to the operational environment.

Business activities such as reservations and charging sessions occur in lower-level aggregates.

---

# 12. Aggregate Composition

The Facility Aggregate is composed of:

## Entity

* Facility

---

## Value Objects

* Facility Type
* Location
* Operating Hours
* Time Zone

---

## Child Aggregates

* Charging Station

Charging Stations are introduced in the next specification.

---

# 13. Entity Definition

## Facility

The Facility entity represents a physical location where charging infrastructure is installed.

### Identity

Every Facility possesses a unique identifier.

Identity remains constant throughout its lifecycle.

---

### Mutable Attributes

The following attributes may change over time:

* name;
* description;
* operational status;
* operating hours;
* location.

Changing these attributes shall not change the Facility identity.

---

### Immutable Attributes

The following attributes should remain immutable after creation:

* identifier;
* creation timestamp.

---

# 14. Value Objects

The Facility Aggregate introduces several reusable Value Objects.

---

## Facility Type

Represents the business classification of the operational environment.

Initial values include:

```text
Residential

Commercial

University

Industrial

Public Parking

Shopping Center

Corporate Campus
```

Future values may be added without affecting existing facilities.

---

## Location

Represents the geographical location.

Initial attributes:

* street;
* number;
* district;
* city;
* state;
* country.

Future versions may include:

* latitude;
* longitude;
* elevation.

Location is modeled as a Value Object because it has no independent identity.

---

## Operating Hours

Represents the expected opening hours for each day of the week.

Example:

```text
Monday

08:00 — 22:00
```

Operating Hours support:

* reservation validation;
* simulation scheduling;
* analytics segmentation.

Operating Hours are immutable once created.

Changing them results in a new Value Object.

---

## Time Zone

Represents the local civil time of the Facility.

Examples:

```text
America/Sao_Paulo

Europe/Berlin

America/New_York
```

Time Zone ensures that reservations, simulations and predictions are evaluated using local business time.

---

# 15. Aggregate Responsibilities

The Facility Aggregate owns the following responsibilities.

## Infrastructure Organization

Provide organizational structure for charging infrastructure.

---

## Operational Context

Represent the environment in which charging infrastructure operates.

---

## Scheduling Context

Provide operating schedules used by downstream business processes.

---

## Analytics Context

Provide the highest aggregation level for KPIs.

Examples:

* Charging Occupancy Rate;
* Connector Utilization;
* Reservation Rate.

---

## Prediction Context

Predictions are associated with Facilities because demand depends strongly on the operational characteristics of each environment.

Example:

> Predict charging infrastructure occupancy for the University Campus tomorrow between 18:00 and 19:00.

---

# 16. Relationships

The Facility Aggregate participates in the following relationships.

| Relationship                | Cardinality |
| --------------------------- | ----------- |
| Facility → Charging Station | 1:N         |
| Facility → Reservation      | indirect    |
| Facility → Charging Session | indirect    |
| Facility → Telemetry        | indirect    |
| Facility → Prediction       | 1:N         |
| Facility → Analytics        | 1:N         |

The Facility never owns Reservations directly.

---

# 17. Ownership Rules

Ownership follows the hierarchy below.

```text
Facility

↓

Charging Station

↓

Connector

↓

Reservation

↓

Charging Session

↓

Telemetry
```

Each Aggregate owns only its immediate business responsibility.

This prevents excessive coupling between domain concepts.

---

# 18. Lifecycle

The Facility lifecycle is intentionally stable.

```text
Created

    │

    ▼

Active

    │

    ├──────────────► Under Maintenance

    │                      │

    │                      ▼

    └────────────────────► Active

    │

    ▼

Inactive
```

Deletion is intentionally omitted.

Facilities represent historical business context and should remain available for analytical purposes even after becoming inactive.

---

# 19. Business Invariants

The following invariants shall always hold.

* Every Facility possesses a unique identity.
* Every Charging Station belongs to exactly one Facility.
* Every Facility defines exactly one Time Zone.
* Every Facility possesses exactly one Facility Type.
* Every Facility may define Operating Hours.
* Historical analytical data shall remain associated with the original Facility.
* Deactivating a Facility shall not remove historical information.

Violation of these invariants constitutes a business error.

---

# 20. Business Rules

The following business rules define the expected behavior of the Facility Aggregate.

Implementation details are intentionally deferred to later specifications.

---

## BR-001 — Facility Creation

A Facility shall be created before any Charging Station can be registered.

Charging infrastructure cannot exist without an operational context.

---

## BR-002 — Unique Name

Facility names should be unique within the same organization.

This simplifies administration and reporting.

Future multi-tenant scenarios may scope uniqueness by tenant.

---

## BR-003 — Facility Activation

Only Facilities in the **Active** state may receive new Charging Stations, Reservations and Charging Sessions.

Inactive or Under Maintenance Facilities reject new operational activities.

---

## BR-004 — Historical Preservation

Changing a Facility shall never invalidate historical operational data.

Reservations, Charging Sessions, Telemetry and Predictions remain associated with the Facility where they originally occurred.

---

## BR-005 — Operational Schedule

Operating Hours define the expected availability of the charging infrastructure.

Business capabilities may use this information to:

* validate reservations;
* generate simulation scenarios;
* segment analytics;
* improve prediction accuracy.

---

## BR-006 — Facility Ownership

A Charging Station may belong to only one Facility.

Ownership transfer is outside the scope of the current version.

---

## BR-007 — Time Zone Consistency

All timestamps presented to users shall respect the Facility Time Zone.

Internal persistence may use UTC.

Business interpretation shall always use local time.

---

# 21. Validation Rules

The following validations apply to Facility creation and updates.

| Field              | Validation          |
| ------------------ | ------------------- |
| Name               | Required, non-empty |
| Description        | Optional            |
| Facility Type      | Required            |
| Time Zone          | Required            |
| Operational Status | Required            |
| Operating Hours    | Optional            |
| Location           | Required            |

Additional validations may be introduced in future versions.

---

# 22. Example Facility

The following illustrates a conceptual Facility.

```text id="9uq8cp"
Facility

Name:
Downtown Shopping Center

Type:
Shopping Center

Status:
Active

Time Zone:
America/Sao_Paulo

Operating Hours:
08:00 - 22:00

Charging Stations:
12
```

This example is illustrative only and does not define persistence.

---

# 23. Analytics Perspective

Facility is the primary analytical dimension of the platform.

Typical questions answered at the Facility level include:

* What is the average charging occupancy?
* Which days experience the highest demand?
* How many charging sessions occur daily?
* What is the reservation success rate?
* How long do charging sessions typically last?
* Which Facility experiences the highest utilization?

Facility-level analytics provide strategic information without exposing unnecessary implementation details.

---

# 24. Artificial Intelligence Perspective

Artificial Intelligence consumes Facility context to improve prediction quality.

Relevant Facility characteristics include:

* Facility Type;
* Operating Hours;
* Geographic Location;
* Historical Occupancy;
* Historical Reservation Patterns.

The first prediction supported by SCEP is:

**Charging Infrastructure Occupancy Prediction**

Example:

> Predict connector occupancy for the Corporate Campus tomorrow between 17:00 and 18:00.

Predictions describe the charging infrastructure belonging to a Facility rather than the Facility itself.

---

# 25. Simulation Perspective

The Digital Twin Simulation Engine creates scenarios centered around Facilities.

Each simulation scenario defines:

* Facility Type;
* number of Charging Stations;
* number of Connectors;
* expected demand profile;
* operating schedule;
* arrival patterns;
* reservation probability;
* no-show probability.

Example scenarios include:

* Residential Condominium;
* University Campus;
* Shopping Center;
* Corporate Office;
* Public Parking Facility.

This approach allows experiments to reproduce distinct operational environments.

---

# 26. Domain Events

Facility operations generate the following events.

| Event                       | Description                  |
| --------------------------- | ---------------------------- |
| FacilityCreated             | A new Facility was created   |
| FacilityUpdated             | Facility information changed |
| FacilityActivated           | Facility became operational  |
| FacilityDeactivated         | Facility became unavailable  |
| FacilityMaintenanceStarted  | Maintenance period started   |
| FacilityMaintenanceFinished | Maintenance period ended     |

These events contribute to:

* audit history;
* observability;
* analytics.

---

# 27. Out of Scope

The Facility Aggregate intentionally excludes:

* electrical energy management;
* billing;
* payment processing;
* parking management;
* physical access control;
* charger firmware;
* maintenance scheduling;
* asset inventory.

These concerns may become future bounded contexts but are not part of the current research scope.

---

# 28. Acceptance Criteria

This specification is considered complete when:

* the Facility Aggregate is fully defined;
* responsibilities are clearly established;
* ownership rules are documented;
* Value Objects are identified;
* lifecycle is documented;
* business rules are defined;
* validation rules are documented;
* relationships with other Aggregates are explicit;
* analytical and AI perspectives are established.

Implementation should be possible without requiring additional conceptual clarification.

---

# 29. Relationship with Other Specifications

This specification serves as the foundation for:

* **SPEC-004 — Charging Stations**, which introduces physical charging equipment.
* **SPEC-006 — Reservations**, which validates Reservation requests against Facility context.
* **SPEC-007 — Charging Sessions**, which defines execution within a Facility.
* **SPEC-009 — Domain Events**, which records operational changes associated with Facilities.
* **SPEC-010 — Analytics**, which aggregates operational metrics by Facility.
* **SPEC-011 — Dataset Export**, which will use Facilities as a primary analytical dimension.
* **SPEC-012 — Predictions**, which will forecast charging infrastructure utilization within Facilities.
* **SPEC-013 — Digital Twin Simulation Engine**, whose scenarios will be centered around Facilities.

Every subsequent specification shall treat the Facility as the root operational context of the platform.

---

# 30. Final Considerations

The Facility Aggregate represents considerably more than a physical location.

Within SCEP, a Facility defines the operational environment in which charging infrastructure is observed, simulated and analyzed.

By placing the Facility at the root of the domain hierarchy, the platform establishes a stable business context that supports infrastructure management, reproducible simulations, analytical processing and Artificial Intelligence experiments.

This decision reflects the central objective of SCEP: not to control electric vehicle charging, but to understand and predict the utilization of charging infrastructure through a robust software engineering and research platform.

The Facility Aggregate is therefore considered the primary organizational unit of the Smart Charging Experimentation Platform and the foundation upon which all subsequent business capabilities are built.
