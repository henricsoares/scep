from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.datasets.domain import (
    DatasetType,
    ExportFilters,
    ExportFormat,
    ExportProfile,
    category,
)


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    type: str
    nullable: bool = False
    unit: str | None = None


SESSION_COLUMNS = (
    Column("session_id", "string"),
    Column("reservation_id", "string"),
    Column("owner_id", "string"),
    Column("vehicle_id", "string"),
    Column("facility_id", "string"),
    Column("station_id", "string"),
    Column("connector_id", "string"),
    Column("status", "enum"),
    Column("started_at", "timestamp"),
    Column("ended_at", "timestamp", True),
    Column("created_at", "timestamp"),
    Column("updated_at", "timestamp"),
)

TELEMETRY_COLUMNS = (
    Column("telemetry_sample_id", "string"),
    Column("sample_id", "string"),
    Column("source", "enum"),
    Column("session_id", "string"),
    Column("reservation_id", "string"),
    Column("owner_id", "string"),
    Column("vehicle_id", "string"),
    Column("facility_id", "string"),
    Column("station_id", "string"),
    Column("connector_id", "string"),
    Column("session_status", "enum"),
    Column("session_started_at", "timestamp"),
    Column("session_ended_at", "timestamp", True),
    Column("recorded_at", "timestamp"),
    Column("received_at", "timestamp"),
    Column("power_kw", "decimal", True, "kW"),
    Column("energy_kwh", "decimal", True, "kWh"),
    Column("state_of_charge_percent", "decimal", True, "percent"),
    Column("created_at", "timestamp"),
)

OCCUPANCY_COLUMNS = (
    Column("bucket_from", "timestamp"),
    Column("bucket_to", "timestamp"),
    Column("timezone", "string"),
    Column("facility_id", "string", True),
    Column("station_id", "string", True),
    Column("connector_id", "string", True),
    Column("available_duration_minutes", "decimal", unit="minutes"),
    Column("reserved_duration_minutes", "decimal", unit="minutes"),
    Column("charging_duration_minutes", "decimal", unit="minutes"),
    Column("effective_reserved_charging_duration_minutes", "decimal", unit="minutes"),
    Column("unused_reserved_duration_minutes", "decimal", unit="minutes"),
    Column("reserved_occupancy_rate", "decimal", True, "ratio"),
    Column("effective_occupancy_rate", "decimal", True, "ratio"),
    Column("reserved_time_utilization_rate", "decimal", True, "ratio"),
)

RESEARCH_NAMESPACES = {
    DatasetType.OPERATIONAL_CHARGING_SESSIONS: {
        "session_id": "charging_session",
        "reservation_id": "reservation",
        "owner_id": "owner",
        "vehicle_id": "vehicle",
    },
    DatasetType.OPERATIONAL_TELEMETRY: {
        "telemetry_sample_id": "telemetry_sample",
        "sample_id": "producer_sample",
        "session_id": "charging_session",
        "reservation_id": "reservation",
        "owner_id": "owner",
        "vehicle_id": "vehicle",
    },
    DatasetType.ANALYTICAL_OCCUPANCY: {},
}


def columns_for(dataset_type: DatasetType) -> tuple[Column, ...]:
    return {
        DatasetType.OPERATIONAL_CHARGING_SESSIONS: SESSION_COLUMNS,
        DatasetType.OPERATIONAL_TELEMETRY: TELEMETRY_COLUMNS,
        DatasetType.ANALYTICAL_OCCUPANCY: OCCUPANCY_COLUMNS,
    }[dataset_type]


def pseudonym(secret: str, export_id: UUID, namespace: str, original: Any) -> str:
    canonical = str(original)
    message = f"{export_id}\0{namespace}\0{canonical}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def transform_research(
    rows: list[dict[str, Any]], dataset_type: DatasetType, export_id: UUID, secret: str
) -> list[dict[str, Any]]:
    namespaces = RESEARCH_NAMESPACES[dataset_type]
    return [
        {
            key: (
                pseudonym(secret, export_id, namespaces[key], value)
                if key in namespaces and value is not None
                else value
            )
            for key, value in row.items()
        }
        for row in rows
    ]


def utc_stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return utc_stamp(value)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float | Decimal):
        return format(value, "f")
    rendered = str(value)
    if rendered.startswith(("=", "+", "-", "@")):
        return "'" + rendered
    return rendered


def serialize_csv(rows: list[dict[str, Any]], columns: tuple[Column, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([item.name for item in columns])
    for row in rows:
        writer.writerow([csv_value(row.get(item.name)) for item in columns])
    return stream.getvalue().encode()


def serialize_parquet(rows: list[dict[str, Any]], columns: tuple[Column, ...]) -> bytes:
    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    names = [item.name for item in columns]
    normalized = [{name: row.get(name) for name in names} for row in rows]
    table = (
        pa.Table.from_pylist(normalized) if normalized else pa.table({name: [] for name in names})
    )
    sink = io.BytesIO()
    pq.write_table(table, sink)
    return sink.getvalue()


def build_artifact(
    *,
    export_id: UUID,
    dataset_type: DatasetType,
    profile: ExportProfile,
    format: ExportFormat,
    filters: ExportFilters,
    rows: list[dict[str, Any]],
    data_cutoff_at: datetime,
    generated_at: datetime,
    application_version: str,
    source_revision: str | None,
    key_version: str,
) -> tuple[bytes, bytes, dict[str, Any]]:
    columns = columns_for(dataset_type)
    data = (
        serialize_csv(rows, columns)
        if format == ExportFormat.CSV
        else serialize_parquet(rows, columns)
    )
    data_name = "data.csv" if format == ExportFormat.CSV else "data.parquet"
    digest = hashlib.sha256(data).hexdigest()
    manifest = {
        "manifest_version": "1.0.0",
        "dataset_export_id": str(export_id),
        "dataset_type": dataset_type.value,
        "dataset_category": category(dataset_type).value,
        "export_profile": profile.value,
        "schema_version": "1.0.0",
        "format": format.value,
        "generated_at": utc_stamp(generated_at),
        "data_cutoff_at": utc_stamp(data_cutoff_at),
        "application_version": application_version,
        "source_revision": source_revision,
        "export_configuration": {
            "dataset_type": dataset_type.value,
            "export_profile": profile.value,
            "format": format.value,
            "schema_version": "1.0.0",
            "filters": filters.canonical(),
        },
        "columns": [asdict(item) for item in columns],
        "row_count": len(rows),
        "data_file": data_name,
        "data_file_size_bytes": len(data),
        "data_file_sha256": digest,
        "pseudonymization": {
            "applied": profile == ExportProfile.RESEARCH
            and bool(RESEARCH_NAMESPACES[dataset_type]),
            "scope": "DATASET_EXPORT" if profile == ExportProfile.RESEARCH else None,
            "algorithm_identifier": "HMAC_SHA256_V1" if profile == ExportProfile.RESEARCH else None,
            "key_version": key_version if profile == ExportProfile.RESEARCH else None,
        },
    }
    manifest_bytes = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", manifest_bytes)
        bundle.writestr(data_name, data)
    return archive.getvalue(), data, manifest
