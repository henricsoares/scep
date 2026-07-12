# SPEC-004 — Charging Stations

## Smart Charging Experimentation Platform (SCEP)

**Status:** Approved

**Version:** 1.0

**Document Owner:** Project Team

**Last Update:** 2026

---

# 1. Purpose

This specification defines the management of **Charging Stations** and **Connectors** within the Smart Charging Experimentation Platform.

Charging Stations represent physical charging equipment installed inside a Facility.

Connectors represent the actual operational resources that can be reserved and used by vehicles.

This specification transforms the Facility context into usable charging infrastructure.

---

# 2. Scope

This specification defines:

* Charging Station model;
* Connector model;
* station lifecycle;
* connector lifecycle;
* business rules;
* validation rules;
* REST API contracts;
* persistence model;
* domain events;
* acceptance criteria.

This specification does not define:

* reservations;
* charging sessions;
* telemetry ingestion;
* payment;
* OCPP integration;
* physical charger control.

---

# 3. Business Context

A Facility may contain one or more Charging Stations.

Each Charging Station may contain one or more Connectors.

Reservations and Charging Sessions are never associated directly with a Charging Station. They are associated with a Connector.

```text
Facility

    └── Charging Station

            ├── Connector
            ├── Connector
            └── Connector
```

The Charging Station provides the physical grouping.

The Connector provides the operational unit.

---

# 4. Domain Concepts

## Charging Station

A physical charging device installed inside a Facility.

A Charging Station:

* belongs to exactly one Facility;
* contains one or more Connectors;
* has an operational status;
* may become inactive or under maintenance.

---

## Connector

A physical charging interface available for use by a vehicle.

A Connector:

* belongs to exactly one Charging Station;
* has a connector type;
* has an operational status;
* is the target of Reservations;
* is the target of Charging Sessions.

---

# 5. Charging Station Attributes

A Charging Station shall contain:

* identifier;
* facility identifier;
* name;
* description;
* serial number;
* manufacturer;
* model;
* maximum power;
* operational status;
* created timestamp;
* updated timestamp.

---

# 6. Connector Attributes

A Connector shall contain:

* identifier;
* charging station identifier;
* connector type;
* maximum power;
* operational status;
* created timestamp;
* updated timestamp.

Supported connector types:

* CCS2;
* CHAdeMO;
* NACS;
* Type 2.

---

# 7. Station Status

Charging Station status values:

```text
Active
Inactive
UnderMaintenance
```

## Active

The station is operational.

Connectors may be used according to their own status.

## Inactive

The station is disabled.

No new reservations or charging sessions may be created for its connectors.

## UnderMaintenance

The station is temporarily unavailable.

No new reservations or charging sessions may be created for its connectors.

---

# 8. Connector Status

Connector status values:

```text
Available
Reserved
Charging
OutOfService
```

## Available

The connector can be reserved or used.

## Reserved

The connector has a CONFIRMED or ACTIVE Reservation relevant to its current operational window.
This instantaneous status does not by itself prevent a non-overlapping future Reservation.

## Charging

The connector is currently being used by a Charging Session.

## OutOfService

The connector is unavailable.

---

# 9. Business Rules

## BR-001 — Facility Required

A Charging Station shall not exist without a Facility.

---

## BR-002 — Connector Required

A Charging Station shall contain at least one Connector.

---

## BR-003 — Station Ownership

A Charging Station belongs to exactly one Facility.

Ownership transfer is outside the scope of this version.

---

## BR-004 — Connector Ownership

A Connector belongs to exactly one Charging Station.

---

## BR-005 — Station Inactivation

An inactive Charging Station cannot receive new Reservations or Charging Sessions.

---

## BR-006 — Maintenance Mode

A Charging Station under maintenance cannot receive new Reservations or Charging Sessions.

---

## BR-007 — Connector Availability

A Connector shall be operationally eligible before receiving a new Reservation. OutOfService
Connectors shall reject new Reservations. A current Reserved or Charging state shall not by
itself reject a non-overlapping future Reservation; SPEC-006 defines calendar eligibility for the
proposed interval.

Only an Available Connector may start a direct Charging Session.

---

## BR-008 — Historical Preservation

Charging Stations and Connectors shall not be physically deleted when historical data exists.

They may be deactivated instead.

---

## BR-009 — Connector Type Stability

Connector type should not be changed after creation if historical usage exists.

---

## BR-010 — Station Status Propagation

When a Charging Station becomes Inactive or UnderMaintenance, its Connectors become unavailable for new operational workflows.

---

# 10. REST API Contract

## Create Charging Station

```http
POST /facilities/{facility_id}/stations
```

Creates a Charging Station inside a Facility.

Request:

```json
{
  "name": "Station A",
  "description": "Main entrance charger",
  "serial_number": "SCEP-001",
  "manufacturer": "Generic",
  "model": "AC-22",
  "maximum_power_kw": 22,
  "connectors": [
    {
      "connector_type": "Type2",
      "maximum_power_kw": 22
    }
  ]
}
```

Response:

```json
{
  "id": "station-id",
  "facility_id": "facility-id",
  "name": "Station A",
  "status": "Active",
  "connectors": [
    {
      "id": "connector-id",
      "connector_type": "Type2",
      "status": "Available"
    }
  ]
}
```

---

## List Charging Stations by Facility

```http
GET /facilities/{facility_id}/stations
```

Returns all Charging Stations belonging to a Facility.

---

## Get Charging Station

```http
GET /stations/{station_id}
```

Returns a Charging Station with its Connectors.

---

## Update Charging Station

```http
PATCH /stations/{station_id}
```

Allowed fields:

* name;
* description;
* operational status.

---

## Add Connector

```http
POST /stations/{station_id}/connectors
```

Adds a Connector to an existing Charging Station.

---

## Update Connector Status

```http
PATCH /connectors/{connector_id}/status
```

Request:

```json
{
  "status": "OutOfService"
}
```

---

# 11. Persistence Model

## charging_stations

```text
id
facility_id
name
description
serial_number
manufacturer
model
maximum_power_kw
status
created_at
updated_at
```

## connectors

```text
id
charging_station_id
connector_type
maximum_power_kw
status
created_at
updated_at
```

Indexes:

```text
charging_stations.facility_id
connectors.charging_station_id
connectors.status
```

---

# 12. Domain Events

The following events shall be published.

## ChargingStationCreated

Emitted when a Charging Station is created.

## ChargingStationUpdated

Emitted when station metadata changes.

## ChargingStationActivated

Emitted when a station becomes Active.

## ChargingStationDeactivated

Emitted when a station becomes Inactive.

## ChargingStationMaintenanceStarted

Emitted when a station enters maintenance mode.

## ChargingStationMaintenanceFinished

Emitted when a station leaves maintenance mode.

## ConnectorAdded

Emitted when a Connector is added to a Charging Station.

## ConnectorStatusChanged

Emitted when a Connector changes status.

---

# 13. Validation Rules

| Field                      | Validation                          |
| -------------------------- | ----------------------------------- |
| facility_id                | Must reference an existing Facility |
| name                       | Required, non-empty                 |
| serial_number              | Required, unique                    |
| maximum_power_kw           | Must be greater than zero           |
| connector_type             | Must be supported                   |
| connector maximum_power_kw | Must be greater than zero           |
| status                     | Must be a valid status              |

---

# 14. Security Rules

Charging Station and Connector management operations are protected capabilities.

In the final platform behavior, only authorized users may manage Charging Stations and Connectors.

Required roles:

- Platform Administrator;
- Facility Operator.

Until SPEC-005 — Identity and Access is implemented, these authorization rules may be enforced through a temporary development mechanism or disabled in local development.

The API design must preserve the assumption that these operations will become protected.

Simulation clients may read Charging Station and Connector data but shall not modify infrastructure configuration unless explicitly allowed.

---

# 15. Testing Requirements

Tests shall cover:

* create Charging Station;
* create Charging Station with Connectors;
* reject station without Facility;
* reject station without Connectors;
* list stations by Facility;
* update station metadata;
* update station status;
* add Connector;
* update Connector status;
* publish Domain Events;
* preserve historical records.

---

# 16. Acceptance Criteria

This specification is complete when:

* Charging Stations can be created inside Facilities;
* each station contains at least one Connector;
* Connectors can be listed and inspected;
* station status can be changed;
* connector status can be changed;
* invalid connector types are rejected;
* inactive stations cannot be used by future operational workflows;
* Domain Events are emitted for relevant changes;
* persistence model is implemented;
* tests validate business rules.

---

# 17. Relationship with Other Specifications

Depends on:

* SPEC-002 — Domain Model and Ubiquitous Language
* SPEC-003 — Facilities

Supports:

* SPEC-005 — Identity and Access
* SPEC-006 — Reservations
* SPEC-007 — Charging Sessions
* SPEC-008 — Telemetry
* SPEC-009 — Domain Events
* SPEC-010 — Analytics
* SPEC-011 — Dataset Export
* SPEC-012 — Predictions
* SPEC-013 — Digital Twin Simulation Engine

---

# 18. Final Considerations

Charging Stations and Connectors form the operational infrastructure of SCEP.

The distinction between Station and Connector is fundamental.

Charging Stations provide physical organization.

Connectors provide operational availability.

This specification establishes the foundation for reservations, sessions, telemetry, analytics and prediction, while preserving the platform’s central goal: observing and understanding charging infrastructure utilization rather than controlling electrical energy delivery.
