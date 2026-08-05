from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.datasets.infrastructure import DatasetExportModel


@dataclass(frozen=True, slots=True)
class PredictionDatasetProvenance:
    id: UUID
    requested_by: UUID
    dataset_type: str
    export_profile: str
    status: str
    filters: dict[str, Any]
    completed_at: datetime | None
    artifact_expires_at: datetime | None


class PredictionDatasetProvenanceReadPort(Protocol):
    def get_for_prediction(self, export_id: UUID) -> PredictionDatasetProvenance | None: ...


class DatasetPredictionReader:
    """Dataset-owned read adapter for immutable prediction provenance metadata."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_prediction(self, export_id: UUID) -> PredictionDatasetProvenance | None:
        item = self.session.get(DatasetExportModel, export_id)
        if item is None:
            return None
        return PredictionDatasetProvenance(
            id=item.id,
            requested_by=item.requested_by,
            dataset_type=item.dataset_type,
            export_profile=item.export_profile,
            status=item.status,
            filters=dict(item.filters),
            completed_at=item.completed_at,
            artifact_expires_at=item.artifact_expires_at,
        )
