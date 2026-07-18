from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import fsum
from time import monotonic
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.modules.analytics.application.models import AnalyticsQuery, Metrics, Response, Scope
from app.modules.analytics.application.ports import AnalyticsReader
from app.modules.analytics.metrics import (
    analytics_failed_total,
    analytics_query_duration_seconds,
    analytics_requests_total,
    analytics_returned_buckets_total,
    analytics_success_total,
)
from app.modules.analytics.projections.smart_charging.calculations import (
    FINAL_RESERVED_STATUSES,
    buckets,
    clipped_minutes,
    operating_intervals,
    ratio,
    reservation_metrics,
    session_metrics,
    utc,
)
from app.modules.identity.domain.user import HumanRole, User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _AnalyticsData:
    facilities: tuple[Any, ...]
    stations: tuple[Any, ...]
    connectors: tuple[Any, ...]
    reservations: tuple[Any, ...]
    sessions: tuple[Any, ...]
    telemetry: tuple[Any, ...]


class AnalyticsValidationError(ValueError):
    pass


class AnalyticsNotFoundError(ValueError):
    pass


class AnalyticsAuthorizationError(ValueError):
    pass


class AnalyticsService:
    def __init__(self, repository: AnalyticsReader) -> None:
        self.repository = repository

    def execute(self, endpoint: str, query: AnalyticsQuery, user: User) -> Response:
        analytics_requests_total.labels(endpoint).inc()
        started = monotonic()
        logger.info("analytics_query_started", extra={"analytics_endpoint": endpoint})
        try:
            now = datetime.now(UTC)
            scope = self._scope(query, user)
            result = self._response(endpoint, query, scope, now)
            bucket_count = len(result.get("series", []))
            analytics_success_total.labels(endpoint).inc()
            analytics_returned_buckets_total.labels(endpoint).inc(bucket_count)
            logger.info(
                "analytics_query_completed",
                extra={"analytics_endpoint": endpoint, "bucket_count": bucket_count},
            )
            return result
        except AnalyticsValidationError:
            analytics_failed_total.labels(endpoint, "validation").inc()
            logger.warning("analytics_validation_failed", extra={"analytics_endpoint": endpoint})
            raise
        except AnalyticsAuthorizationError:
            analytics_failed_total.labels(endpoint, "authorization").inc()
            logger.warning("analytics_authorization_failed", extra={"analytics_endpoint": endpoint})
            raise
        except Exception:
            analytics_failed_total.labels(endpoint, "execution").inc()
            logger.exception("analytics_query_failed", extra={"analytics_endpoint": endpoint})
            raise
        finally:
            analytics_query_duration_seconds.labels(endpoint).observe(monotonic() - started)

    def _scope(self, query: AnalyticsQuery, user: User) -> Scope:
        start, end = query.from_, query.to
        if start.tzinfo is None or end.tzinfo is None:
            raise AnalyticsValidationError("from and to must include an explicit timezone offset")
        if utc(start) >= utc(end):
            raise AnalyticsValidationError("from must be earlier than to")
        if utc(end) - utc(start) > timedelta(days=366):
            raise AnalyticsValidationError("analysis window must not exceed 366 days")
        facilities = {item.id: item for item in self.repository.facilities()}
        stations = {item.id: item for item in self.repository.stations()}
        connectors = {item.id: item for item in self.repository.connectors()}
        if query.facility_id and query.facility_id not in facilities:
            raise AnalyticsNotFoundError("facility not found")
        if query.station_id and query.station_id not in stations:
            raise AnalyticsNotFoundError("charging station not found")
        if query.connector_id and query.connector_id not in connectors:
            raise AnalyticsNotFoundError("connector not found")
        if (
            query.station_id
            and query.facility_id
            and stations[query.station_id].facility_id != query.facility_id
        ):
            raise AnalyticsValidationError("charging station does not belong to facility")
        if query.connector_id:
            connector_station = connectors[query.connector_id].charging_station_id
            if query.station_id and connector_station != query.station_id:
                raise AnalyticsValidationError("connector does not belong to charging station")
            if query.facility_id and stations[connector_station].facility_id != query.facility_id:
                raise AnalyticsValidationError("connector does not belong to facility")

        admin = HumanRole.PLATFORM_ADMINISTRATOR in user.roles
        operator = HumanRole.FACILITY_OPERATOR in user.roles
        if not admin and not operator:
            raise AnalyticsAuthorizationError("insufficient permission")
        requested_facilities: set[UUID]
        if query.facility_id:
            requested_facilities = {query.facility_id}
        elif query.station_id:
            requested_facilities = {stations[query.station_id].facility_id}
        elif query.connector_id:
            station_id = connectors[query.connector_id].charging_station_id
            requested_facilities = {stations[station_id].facility_id}
        elif operator and not admin:
            if len(user.facility_ids) != 1:
                raise AnalyticsAuthorizationError("facility operators must query one facility")
            requested_facilities = {user.facility_ids[0]}
        else:
            requested_facilities = set(facilities)
        if operator and not admin and not requested_facilities.issubset(user.facility_ids):
            raise AnalyticsAuthorizationError("facility is outside authorized scope")
        if operator and not admin and len(requested_facilities) != 1:
            raise AnalyticsAuthorizationError("facility operators cannot query multiple facilities")

        station_ids = {
            item.id for item in stations.values() if item.facility_id in requested_facilities
        }
        if query.station_id:
            station_ids &= {query.station_id}
        connector_ids = {
            item.id for item in connectors.values() if item.charging_station_id in station_ids
        }
        if query.connector_id:
            connector_ids &= {query.connector_id}
        timezone = query.timezone
        if timezone is None:
            if len(requested_facilities) != 1:
                raise AnalyticsValidationError("timezone is required for multi-facility queries")
            timezone = facilities[next(iter(requested_facilities))].timezone
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise AnalyticsValidationError("timezone must be a valid IANA time zone") from exc
        return Scope(tuple(sorted(requested_facilities)), tuple(sorted(connector_ids)), timezone)

    def _response(
        self, endpoint: str, query: AnalyticsQuery, scope: Scope, now: datetime
    ) -> Response:
        data = self._load(query.from_, query.to, scope)
        metrics = self._calculate(query.from_, query.to, scope, now, data)
        window = {"from": query.from_, "to": query.to, "timezone": scope.timezone}
        scope_body = {
            "facility_id": query.facility_id,
            "station_id": query.station_id,
            "connector_id": query.connector_id,
        }
        if endpoint == "overview":
            overview_metrics = {key: dict(value) for key, value in metrics.items()}
            overview_metrics["reservations"].pop("average_reservation_duration_minutes", None)
            body: Response = {"window": window, "scope": scope_body, **overview_metrics}
        else:
            key = {
                "reservations": "reservations",
                "charging-sessions": "charging_sessions",
                "occupancy": "capacity",
                "energy": "energy",
            }[endpoint]
            body = {"window": window, "scope": scope_body, "metrics": metrics[key]}
            if query.granularity:
                series = []
                for low, high in buckets(query.from_, query.to, scope.timezone, query.granularity):
                    item_metrics = self._calculate(low, high, scope, now, data)[key]
                    series.append({"from": low, "to": high, "metrics": item_metrics})
                body["series"] = series
        return body

    def _load(self, start: datetime, end: datetime, scope: Scope) -> _AnalyticsData:
        facilities = tuple(
            item for item in self.repository.facilities() if item.id in scope.facility_ids
        )
        facility_ids = {item.id for item in facilities}
        stations = tuple(
            item for item in self.repository.stations() if item.facility_id in facility_ids
        )
        connectors = tuple(
            item for item in self.repository.connectors() if item.id in scope.connector_ids
        )
        overlapping_sessions = self.repository.sessions(scope.connector_ids, utc(start), utc(end))
        reservations = self.repository.reservations(
            scope.connector_ids,
            utc(start),
            utc(end),
            tuple(item.reservation_id for item in overlapping_sessions),
        )
        selected_reservation_ids = tuple(
            item.id for item in reservations if utc(start) <= utc(item.start_at) < utc(end)
        )
        sessions = tuple(
            self.repository.sessions(
                scope.connector_ids, utc(start), utc(end), selected_reservation_ids
            )
        )
        selected_sessions = [
            item for item in sessions if utc(start) <= utc(item.started_at) < utc(end)
        ]
        telemetry = tuple(
            self.repository.telemetry(
                tuple(item.id for item in selected_sessions), utc(start), utc(end)
            )
        )
        return _AnalyticsData(
            facilities,
            stations,
            connectors,
            tuple(reservations),
            sessions,
            telemetry,
        )

    def _calculate(
        self,
        start: datetime,
        end: datetime,
        scope: Scope,
        now: datetime,
        data: _AnalyticsData,
    ) -> dict[str, Metrics]:
        facilities = {item.id: item for item in data.facilities}
        stations = {item.id: item for item in data.stations}
        connectors = {item.id: item for item in data.connectors}
        connector_facility = {
            connector.id: facilities[stations[connector.charging_station_id].facility_id]
            for connector in connectors.values()
        }
        operating = {
            facility.id: operating_intervals(
                start, end, facility.timezone, facility.operating_hours
            )
            for facility in facilities.values()
        }
        available = fsum(
            clipped_minutes(start, end, operating[connector_facility[item].id])
            for item in connectors
        )
        reservations = [
            item
            for item in data.reservations
            if (utc(item.start_at) < utc(end) and utc(item.end_at) > utc(start))
            or utc(start) <= utc(item.start_at) < utc(end)
        ]
        sessions = [
            item
            for item in data.sessions
            if (
                utc(item.started_at) < utc(end)
                and (item.ended_at is None or utc(item.ended_at) > utc(start))
            )
            or utc(start) <= utc(item.started_at) < utc(end)
        ]
        reservations_by_id = {item.id: item for item in data.reservations}
        sessions_by_reservation = {item.reservation_id: item for item in data.sessions}
        selected_reservations = [
            item for item in reservations if utc(start) <= utc(item.start_at) < utc(end)
        ]
        selected_sessions = [
            item for item in sessions if utc(start) <= utc(item.started_at) < utc(end)
        ]
        reserved_values = [
            (
                clipped_minutes(
                    item.start_at, item.end_at, operating[connector_facility[item.connector_id].id]
                )
                if item.status in FINAL_RESERVED_STATUSES
                else 0.0
            )
            for item in reservations
        ]
        selected_reserved_values = [
            (
                clipped_minutes(
                    item.start_at,
                    item.end_at,
                    operating[connector_facility[item.connector_id].id],
                )
                if item.status in FINAL_RESERVED_STATUSES
                else 0.0
            )
            for item in selected_reservations
        ]
        session_values: dict[UUID, float] = {}
        effective_reserved = 0.0
        for item in sessions:
            effective_end = min(utc(item.ended_at) if item.ended_at else now, utc(end))
            duration = clipped_minutes(
                item.started_at, effective_end, operating[connector_facility[item.connector_id].id]
            )
            session_values[item.id] = duration
            reservation = reservations_by_id.get(item.reservation_id)
            if reservation:
                low, high = max(utc(item.started_at), utc(reservation.start_at)), min(
                    effective_end, utc(reservation.end_at)
                )
                if low < high:
                    effective_reserved += clipped_minutes(
                        low, high, operating[connector_facility[item.connector_id].id]
                    )
        selected_session_values = [session_values[item.id] for item in selected_sessions]
        reserved = fsum(reserved_values)
        charging = fsum(session_values.values())
        capacity: Metrics = {
            "available_duration_minutes": round(available, 6),
            "reserved_duration_minutes": round(reserved, 6),
            "charging_duration_minutes": round(charging, 6),
            "effective_reserved_charging_duration_minutes": round(effective_reserved, 6),
            "unused_reserved_duration_minutes": round(max(0.0, reserved - effective_reserved), 6),
            "reserved_occupancy_rate": ratio(reserved, available),
            "effective_occupancy_rate": ratio(charging, available),
            "reserved_time_utilization_rate": ratio(effective_reserved, reserved),
        }
        selected_session_ids = {item.id for item in selected_sessions}
        telemetry = [
            item
            for item in data.telemetry
            if item.session_id in selected_session_ids
            and utc(start) <= utc(item.recorded_at) < utc(end)
        ]
        maxima: dict[UUID, float] = {}
        for sample in telemetry:
            if sample.energy_kwh is not None:
                maxima[sample.session_id] = max(
                    maxima.get(sample.session_id, sample.energy_kwh), sample.energy_kwh
                )
        energy_total = fsum(maxima.values())
        energy: Metrics = {
            "total_delivered_energy_kwh": round(energy_total, 6),
            "sessions_with_energy_data": len(maxima),
            "sessions_without_energy_data": len(selected_sessions) - len(maxima),
            "average_energy_per_session_kwh": ratio(energy_total, len(maxima)),
        }
        return {
            "reservations": reservation_metrics(
                selected_reservations, sessions_by_reservation, selected_reserved_values
            ),
            "capacity": capacity,
            "charging_sessions": session_metrics(
                selected_sessions, reservations_by_id, selected_session_values
            ),
            "energy": energy,
        }
