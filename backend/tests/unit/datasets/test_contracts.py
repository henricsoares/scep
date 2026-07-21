from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from uuid import uuid4

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from app.modules.datasets import metrics
from app.modules.datasets.domain import (
    DatasetType,
    ExportFilters,
    ExportFormat,
    ExportProfile,
    FailureCode,
    recovery_failure,
)
from app.modules.datasets.schemas import (
    SESSION_COLUMNS,
    build_artifact,
    csv_value,
    pseudonym,
    serialize_csv,
    serialize_parquet,
    transform_research,
)
from app.modules.datasets.storage import ArtifactStorageError, LocalDatasetArtifactStorage
from prometheus_client import generate_latest


def now() -> datetime:
    return datetime(2026, 7, 21, 12, tzinfo=UTC)


def session_row() -> dict[str, object]:
    return {
        "session_id": uuid4(),
        "reservation_id": uuid4(),
        "owner_id": uuid4(),
        "vehicle_id": uuid4(),
        "facility_id": uuid4(),
        "station_id": uuid4(),
        "connector_id": uuid4(),
        "status": "COMPLETED",
        "started_at": now(),
        "ended_at": None,
        "created_at": now(),
        "updated_at": now(),
    }


def test_pseudonymization_is_export_scoped_and_namespace_separated() -> None:
    first, second = uuid4(), uuid4()
    source = uuid4()
    assert pseudonym("secret", first, "owner", source) == pseudonym(
        "secret", first, "owner", source
    )
    assert pseudonym("secret", first, "owner", source) != pseudonym(
        "secret", first, "vehicle", source
    )
    assert pseudonym("secret", first, "owner", source) != pseudonym(
        "secret", second, "owner", source
    )
    assert len(pseudonym("secret", first, "owner", source)) == 64


def test_failure_code_contract_is_closed_and_snapshot_loss_takes_precedence() -> None:
    assert {item.value for item in FailureCode} == {
        "ROW_LIMIT_EXCEEDED",
        "ARTIFACT_SIZE_LIMIT_EXCEEDED",
        "PROCESSING_TIMEOUT",
        "STORAGE_FAILURE",
        "GENERATION_FAILURE",
        "SNAPSHOT_LOST",
        "ABANDONED_PROCESSING",
    }
    assert recovery_failure(snapshot_lost=True) == FailureCode.SNAPSHOT_LOST
    assert recovery_failure(snapshot_lost=False) == FailureCode.ABANDONED_PROCESSING


def test_research_transform_preserves_infrastructure_and_referential_integrity() -> None:
    export_id = uuid4()
    row = session_row()
    transformed = transform_research(
        [row, dict(row)], DatasetType.OPERATIONAL_CHARGING_SESSIONS, export_id, "secret"
    )
    assert transformed[0]["session_id"] == transformed[1]["session_id"]
    assert transformed[0]["session_id"] != row["session_id"]
    assert transformed[0]["facility_id"] == row["facility_id"]


def test_csv_contract_null_timestamp_and_formula_protection() -> None:
    row = session_row()
    row["status"] = "=unsafe"
    content = serialize_csv([row], SESSION_COLUMNS).decode()
    parsed = list(csv.DictReader(io.StringIO(content)))
    assert content.endswith("\n")
    assert parsed[0]["ended_at"] == ""
    assert parsed[0]["started_at"].endswith("Z")
    assert parsed[0]["status"] == "'=unsafe"


@pytest.mark.parametrize("format", [ExportFormat.CSV, ExportFormat.PARQUET])
def test_zip_manifest_checksum_and_exact_entries(format: ExportFormat) -> None:
    export_id = uuid4()
    row = session_row()
    artifact, data, manifest = build_artifact(
        export_id=export_id,
        dataset_type=DatasetType.OPERATIONAL_CHARGING_SESSIONS,
        profile=ExportProfile.ADMINISTRATIVE,
        format=format,
        filters=ExportFilters(now(), now().replace(day=22)),
        rows=[row],
        data_cutoff_at=now(),
        generated_at=now(),
        application_version="1.0.0",
        source_revision="abc123",
        key_version="v1",
    )
    with zipfile.ZipFile(io.BytesIO(artifact)) as bundle:
        expected_data = "data.csv" if format == ExportFormat.CSV else "data.parquet"
        assert set(bundle.namelist()) == {"manifest.json", expected_data}
        assert all(not name.startswith(("/", "../")) for name in bundle.namelist())
        embedded = json.loads(bundle.read("manifest.json"))
        assert embedded == manifest
        assert bundle.read(expected_data) == data
    assert manifest["data_file_sha256"] == hashlib.sha256(data).hexdigest()
    assert [item["name"] for item in manifest["columns"]] == [item.name for item in SESSION_COLUMNS]
    assert set(manifest) == {
        "manifest_version",
        "dataset_export_id",
        "dataset_type",
        "dataset_category",
        "export_profile",
        "schema_version",
        "format",
        "generated_at",
        "data_cutoff_at",
        "application_version",
        "source_revision",
        "export_configuration",
        "columns",
        "row_count",
        "data_file",
        "data_file_size_bytes",
        "data_file_sha256",
        "pseudonymization",
    }
    assert manifest["manifest_version"] == manifest["schema_version"] == "1.0.0"
    assert manifest["row_count"] == 1
    if format == ExportFormat.PARQUET:
        table = pq.read_table(io.BytesIO(data))
        assert table.column_names == [item.name for item in SESSION_COLUMNS]
        assert table.num_rows == 1
        values = table.to_pylist()[0]
        assert str(values["session_id"]) == str(row["session_id"])
        assert values["ended_at"] is None
        assert values["status"] == row["status"]


def test_csv_and_parquet_are_logically_equivalent() -> None:
    row = session_row()
    csv_rows = list(csv.DictReader(io.StringIO(serialize_csv([row], SESSION_COLUMNS).decode())))
    parquet_rows = pq.read_table(io.BytesIO(serialize_parquet([row], SESSION_COLUMNS))).to_pylist()
    assert list(csv_rows[0]) == [column.name for column in SESSION_COLUMNS]
    assert csv_rows == [
        {column.name: csv_value(parquet_rows[0][column.name]) for column in SESSION_COLUMNS}
    ]


def test_local_storage_is_atomic_and_rejects_traversal(tmp_path: object) -> None:
    storage = LocalDatasetArtifactStorage(str(tmp_path))
    export_id = uuid4()
    key = storage.store(export_id, b"artifact")
    assert storage.exists(key)
    with storage.open(key) as stream:
        assert stream.read() == b"artifact"
    assert not list(storage.root.glob(".partial-*"))
    with pytest.raises(ArtifactStorageError):
        storage.exists("../artifact.zip")
    storage.delete(key)
    assert not storage.exists(key)


def test_observability_metrics_are_exposed_without_identifier_labels() -> None:
    exposition = generate_latest().decode()
    expected = {
        "scep_dataset_export_requests_total",
        "scep_dataset_export_outcomes_total",
        "scep_dataset_export_failures_total",
        "scep_dataset_export_processing_duration_seconds",
        "scep_dataset_export_pending_duration_seconds",
        "scep_dataset_export_generated_rows",
        "scep_dataset_export_artifact_size_bytes",
        "scep_dataset_exports_currently_processing",
        "scep_dataset_export_expired_artifacts_total",
        "scep_dataset_export_storage_failures_total",
    }
    assert all(name in exposition for name in expected)
    collectors = (
        metrics.export_requests_total,
        metrics.export_outcomes_total,
        metrics.export_failures_total,
        metrics.storage_failures_total,
    )
    forbidden = {"dataset_export_id", "actor_id", "facility_id", "station_id", "connector_id"}
    assert all(forbidden.isdisjoint(collector._labelnames) for collector in collectors)
