# API Client Collections

## Insomnia

Import `scep-insomnia.json` using **Import → File**. The collection points to
`http://localhost:8000` and includes the bootstrap administrator credentials from
`.env.example`.

Do not commit real access tokens or non-local credentials to the collection.

## SPEC-006 visual acceptance

Start the complete local stack before running the collection:

```bash
make up
docker compose ps
```

The API, Grafana and Prometheus must be available at:

- API: `http://localhost:8000`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`

Use a clean database or change the example Facility names, station serial numbers and user
emails before repeating the setup. These fields are unique.

### 1. Review the environment

Before creating Reservations, replace all example timestamp variables with future timestamps
that include `Z` or an explicit offset such as `-03:00`.

Keep these relationships:

- `start_at`–`end_at`: a one-hour interval;
- `adjacent_start_at`: exactly equal to `end_at`;
- `overlap_start_at`–`overlap_end_at`: overlaps the first interval;
- `rescheduled_start_at`–`rescheduled_end_at`: an unused interval more than 60 minutes away;
- `visibility_start_at`–`visibility_end_at`: an unused interval distinct from the first one;
- `late_start_at`: approximately 30 minutes from now;
- `no_show_start_at`: approximately one minute from now;
- `no_show_end_at`: at least 15 minutes after `no_show_start_at`.
- `no_show_replacement_start_at`: update to approximately one minute in the future after the
  No-Show grace period has elapsed; it must remain at least 15 minutes before `no_show_end_at`.

The default values are examples only and must be adjusted on the day of validation.

### 2. Authenticate the administrator

Run **Authentication → Login** and copy `access_token` to the environment variable
`access_token`. Tokens expire after 30 minutes in the default local configuration.

### 3. Run SPEC-006 setup

Run **SPEC-006 - 0 Setup** in numeric order. After each response, copy identifiers as follows:

| Request | Response field | Environment variable |
| --- | --- | --- |
| Create Managed Facility | `id` | `facility_id` |
| Create Outside Facility | `id` | `outside_facility_id` |
| Create Managed Station | `id` | `station_id` |
| Create Managed Station | `connectors[0].id` | `connector_id` |
| Create Managed Station | `connectors[1].id` | `alternate_connector_id` |
| Create Outside Station | `id` | `outside_station_id` |
| Create Outside Station | `connectors[0].id` | `outside_connector_id` |
| Create Outside Station | `connectors[1].id` | `outside_alternate_connector_id` |
| Create EV Driver | `id` | `driver_id` |
| Create Facility Operator | `id` | `operator_id` |
| Create Technical Client | `id` | `technical_id` |

The Facility Operator is assigned only to `facility_id`.

### 4. Authenticate the test identities

Run the three role-specific requests in **Authentication** and copy each `access_token`:

- EV Driver → `driver_token`;
- Facility Operator → `operator_token`;
- Technical Client → `technical_token`.

### 5. Create Vehicles

Run **SPEC-006 - Vehicles** in numeric order. Copy the IDs returned by requests 01–04 to:

- `vehicle_id`;
- `second_vehicle_id`;
- `third_vehicle_id`;
- `operator_vehicle_id`.

Expected results:

- owned Vehicles are created with status `ACTIVE`;
- the Driver list contains only the Driver's Vehicles;
- rename succeeds;
- a foreign Vehicle returns `404` instead of revealing its existence;
- an empty patch returns `422`.

To test inactive Vehicle eligibility, change request 07 temporarily to
`{"status":"INACTIVE"}`, attempt to create a Reservation and expect `422`. Restore it with
`{"status":"ACTIVE"}` afterward.

### 6. Validate Facility Operator visibility

Run **SPEC-006 - Operator Visibility** in order. Save the created Reservation IDs before
continuing:

| Reservation | Environment variable |
| --- | --- |
| A — Operator-owned outside managed Facilities | `reservation_id` |
| B — Driver-owned inside the managed Facility | `second_reservation_id` |
| C — Driver-owned outside both scopes | `concealed_reservation_id` |

Acceptance criteria:

- `GET /reservations` as Facility Operator returns A and B only;
- detail A returns `200` through ownership;
- detail B returns `200` through Facility scope;
- detail C returns `404` through concealment;
- changing B returns `403`, because Facility scope grants read access but not ownership.

This validates `OWNERSHIP OR FACILITY_SCOPE`. Run this group before the general Reservation
group so unrelated managed-Facility Reservations do not appear in its unfiltered list.

### 7. Validate the Reservation lifecycle

Run **SPEC-006 - Reservations** in numeric order. Request 01 creates the main Reservation; copy
its `reservation.id` to `reservation_id`, replacing the value from the completed visibility
scenario.

Expected results:

1. creation returns `201`, status `CONFIRMED` and an empty `warnings` list;
2. list filters by status and supports the disabled owner/resource/time filters and pagination;
3. detail returns the owned Reservation;
4. Connector calendar returns visible Reservations for that Connector;
5. the adjacent half-open interval succeeds and returns `BACK_TO_BACK_RESERVATION`;
6. overlap on the same Connector returns `409` and `CONNECTOR_RESERVATION_CONFLICT`;
7. overlap for the same Vehicle on another Connector returns `409` and
   `VEHICLE_RESERVATION_CONFLICT`;
8. rescheduling a distant `CONFIRMED` Reservation succeeds;
9. cancellation more than 60 minutes before its start produces `CANCELLED` without warnings;
10. the near-term Reservation is created; copy its ID to `second_reservation_id`;
11. cancelling it produces `LATE_CANCELLED` and `LATE_CANCELLATION`;
12. timestamps without an explicit offset return `422`;
13. an empty patch returns `422`.

Responses normalize valid timestamps to UTC. Additional boundary checks can be made by editing
request 01:

- start in the past → `422`;
- start at or after end → `422`;
- duration below 15 minutes → `422`;
- duration above 24 hours → `422`;
- explicit `null` in a patch → `422`.

To validate Connector eligibility, run **Charging Stations → Update Connector Status** with
`OutOfService`, attempt request 01 and expect `422`, then restore the Connector to `Available`.

### 8. Validate No-Show

Set `no_show_start_at` to approximately one minute in the future and run request 14. Copy its
`reservation.id` to `no_show_reservation_id`.

After the instant `no_show_start_at + 15 minutes` has passed, run request 15. The read triggers
opportunistic reconciliation and must return:

- status `NO_SHOW`;
- a populated `no_show_at`.

Set `no_show_replacement_start_at` to approximately one minute in the future and run request 16.
It overlaps the remaining portion of the original interval and must return `201`, proving the
No-Show released both the Vehicle and Connector calendars.

### 9. Validate the Technical Client

Run **SPEC-006 - Technical Client** in order. Copy the Vehicle ID from request 01 to
`technical_vehicle_id` and the Reservation ID from request 02 to `technical_reservation_id`.

The Technical Client must manage its owned Vehicle and Reservation, list only owned
Reservations, and receive `404` for the foreign `concealed_reservation_id`.

## Grafana acceptance

Allow approximately 5–15 seconds after an API request for OpenTelemetry batching and Prometheus
scraping. In a clean Grafana installation the initial login is normally `admin` / `admin`.

### Datasources

Open **Connections → Data sources** and run **Save & test** for Prometheus, Loki and Tempo.

### Prometheus

Open **Explore**, select Prometheus and verify:

```promql
up{job="backend"}
```

The result must be `1`. Then inspect the SPEC-006 counters:

```promql
scep_reservations_created_total
```

```promql
sum by (classification) (scep_reservations_cancelled_total)
```

```promql
sum by (resource) (scep_reservation_conflicts_total)
```

```promql
scep_reservations_no_show_total
```

The executed scenarios must produce cancellation classifications `normal` and `late`, and
conflict resources `connector` and `vehicle`. After the delayed reconciliation, the No-Show
counter must increase.

HTTP traffic can be inspected with:

```promql
sum by (handler, method, status) (
  increase(http_requests_total{handler=~"/reservations.*|/vehicles.*"}[15m])
)
```

### Loki

In **Explore**, select Loki and use:

```logql
{service_name="scep-backend"} |= "reservation"
```

Expected application messages include:

- `reservation created` with status `CONFIRMED`;
- `reservation cancelled` with classification `normal` or `late`;
- `reservation no-show reconciliation completed` after the No-Show scenario.

The collection sends stable `X-Request-ID` values for the principal scenarios. For example:

```logql
{service_name="scep-backend"} | request_id="spec006-create-main"
```

Expand `HTTP request completed` and verify `request_id`, `correlation_id`, `http_method`, `route`,
`status_code`, `execution_time_ms`, `trace_id` and `span_id`. If the Loki installation exposes a
different normalized service label, locate the value `scep-backend` through the label browser.

### Tempo and log/trace correlation

Expand a Loki result and follow its derived `TraceID` link to Tempo. If the link is not rendered,
copy the 32-character `trace_id` field and search for it directly in Tempo.

The trace must show:

- resource service name `scep-backend`;
- the corresponding `/reservations` or `/vehicles` server span;
- HTTP method and status;
- `http.request_id` and `correlation.id` matching Insomnia and Loki.

From Tempo, **Logs for this span** must return the Loki entries for the same Trace ID. The visual
acceptance chain is therefore:

```text
Insomnia X-Request-ID
  → Loki request_id and trace_id
  → Tempo trace
  → Prometheus Reservation counter
```

## Scope notes

SPEC-006 does not expose public activation or completion endpoints; these transitions are domain
operations reserved for the future Charging Session integration. PostgreSQL concurrent-write
protection is validated by the dedicated integration test rather than by sequential Insomnia
requests.
