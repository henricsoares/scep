from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

import httpx

from app.scenarios.planner import (
    ConnectorCandidate,
    DriverInventory,
    Operation,
    PlannedEvent,
)


class DomainRejected(Exception):
    def __init__(self, status_code: int, code: str | None, detail: object) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(f"backend rejected request with HTTP {status_code}: {detail}")


async def fetch_backend_health(
    backend_url: str,
    *,
    max_attempts: int = 12,
    retry_delay_seconds: float = 5.0,
) -> dict[str, object]:
    max_attempts = max(max_attempts, 1)
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.get(f"{backend_url.rstrip('/')}/health")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < max_attempts:
                    await asyncio.sleep(retry_delay_seconds)
    raise RuntimeError(
        f"Backend health endpoint was unavailable after {max_attempts} attempts"
    ) from last_error


class BackendClient:
    def __init__(
        self,
        backend_url: str,
        run_id: UUID,
        run_token: str,
        driver_tokens: dict[UUID, str],
        *,
        timeout_seconds: float = 20,
        max_attempts: int = 4,
    ) -> None:
        self.run_id = run_id
        self.run_token = run_token
        self.driver_tokens = driver_tokens
        self.max_attempts = max_attempts
        self.http = httpx.AsyncClient(
            base_url=backend_url.rstrip("/"), timeout=timeout_seconds
        )

    async def close(self) -> None:
        await self.http.aclose()

    async def inventory(
        self, driver_id: UUID, facility_ids: list[UUID]
    ) -> DriverInventory:
        headers = self._bearer(driver_id)
        vehicles_response = await self.http.get("/vehicles", headers=headers)
        vehicles_response.raise_for_status()
        vehicle_ids = [
            UUID(item["id"])
            for item in vehicles_response.json()
            if item.get("status") == "ACTIVE"
        ]
        connectors: list[ConnectorCandidate] = []
        for facility_id in sorted(facility_ids, key=str):
            response = await self.http.get(
                f"/facilities/{facility_id}/stations", headers=headers
            )
            response.raise_for_status()
            for station in response.json():
                if station.get("status") != "Active":
                    continue
                for connector in station.get("connectors", []):
                    if connector.get("status") not in {"Available", "Reserved"}:
                        continue
                    connectors.append(
                        ConnectorCandidate(
                            id=connector["id"],
                            facility_id=facility_id,
                            connector_type=connector["connector_type"],
                            maximum_power_kw=connector["maximum_power_kw"],
                        )
                    )
        return DriverInventory(
            driver_id=driver_id, vehicle_ids=vehicle_ids, connectors=connectors
        )

    async def execute(
        self, event: PlannedEvent, resource_ids: dict[UUID, UUID]
    ) -> tuple[dict[str, object] | list[object], int]:
        path, payload = self._request(event, resource_ids)
        headers = self._bearer(event.driver_id) | {
            "X-Simulation-Token": self.run_token,
            "X-Simulation-Run-Id": str(self.run_id),
            "X-Simulated-At": event.simulated_at.isoformat(),
            "X-Simulation-Event-Id": str(event.event_id),
        }
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                response = await self.http.post(
                    path, headers=headers, json=payload or None
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
            else:
                if response.status_code < 300:
                    return response.json(), attempt
                detail = response.json().get("detail")
                code = detail.get("code") if isinstance(detail, dict) else None
                if response.status_code < 500:
                    raise DomainRejected(response.status_code, code, detail)
                last_error = RuntimeError(
                    f"backend returned HTTP {response.status_code}"
                )
            if attempt + 1 < self.max_attempts:
                await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
        raise RuntimeError("simulated request exhausted retry policy") from last_error

    def _bearer(self, driver_id: UUID) -> dict[str, str]:
        token = self.driver_tokens.get(driver_id)
        if token is None:
            raise ValueError(f"missing bearer token for EVDriver {driver_id}")
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _request(
        event: PlannedEvent, resource_ids: dict[UUID, UUID]
    ) -> tuple[str, dict[str, object]]:
        dependency = (
            None if event.depends_on is None else resource_ids.get(event.depends_on)
        )
        if event.operation == Operation.RESERVATION_CREATE:
            return "/reservations", event.payload
        if dependency is None:
            raise RuntimeError(
                f"dependency for event {event.event_id} has no resource result"
            )
        if event.operation == Operation.RESERVATION_CANCEL:
            return f"/reservations/{dependency}/cancel", {}
        if event.operation == Operation.SESSION_ACTIVATE:
            return f"/reservations/{dependency}/charging-session", {}
        if event.operation == Operation.SESSION_COMPLETE:
            return f"/charging-sessions/{dependency}/complete", {}
        if event.operation == Operation.TELEMETRY_BATCH_CREATE:
            return f"/charging-sessions/{dependency}/telemetry/batch", event.payload
        raise ValueError(f"unsupported operation {event.operation}")


def response_resource(
    operation: Operation, body: dict[str, object] | list[object]
) -> UUID | None:
    if isinstance(body, list):
        return None
    if operation in {Operation.RESERVATION_CREATE, Operation.RESERVATION_CANCEL}:
        reservation = body.get("reservation")
        return UUID(reservation["id"]) if isinstance(reservation, dict) else None
    identifier = body.get("id")
    return None if identifier is None else UUID(str(identifier))


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
