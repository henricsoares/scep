from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.prediction_reader import ChargingPredictionReader
from app.modules.datasets.prediction import DatasetPredictionReader
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.modules.prediction.domain import (
    PredictionBucket,
    PredictionScope,
    PredictionScopeType,
    PublicationContent,
    Weekday,
)
from app.modules.prediction.infrastructure import (
    WeeklyOccupancyPredictionCurrentModel,
    WeeklyOccupancyPredictionPublicationModel,
)
from app.modules.prediction.service import PredictionService, PublicationResult
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="POSTGRES_TEST_DATABASE_URL is required for concurrency integration tests",
)


def _content(facility_id: UUID, run_id: str, generated_at: datetime) -> PublicationContent:
    return PublicationContent.create(
        scope=PredictionScope(PredictionScopeType.FACILITY, facility_id),
        timezone="UTC",
        contract_version="1.0",
        model_name="concurrency-baseline",
        model_version="1",
        external_run_id=run_id,
        generated_at=generated_at,
        dataset_export_id=None,
        training_data_from=None,
        training_data_to=None,
        buckets=[PredictionBucket(day, hour, 0.25) for day in Weekday for hour in range(24)],
    )


def test_concurrent_publications_serialize_current_selection() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    facility_id = uuid4()
    with sessions() as db:
        db.add(
            FacilityModel(
                id=facility_id,
                name=f"Prediction concurrency {facility_id}",
                facility_type="University",
                timezone="UTC",
                country="Brazil",
                city="Juiz de Fora",
                address="Campus",
                operating_hours=None,
                status="Active",
            )
        )
        db.commit()
        publisher = SqlAlchemyUserRepository(db).add(
            User.create(
                email=f"prediction-concurrency-{uuid4()}@example.com",
                display_name="Prediction concurrency publisher",
                password_hash="test-password-hash",
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.PLATFORM_ADMINISTRATOR],
                facility_ids=[],
            )
        )

    generated = datetime(2026, 8, 5, 12, tzinfo=UTC)
    contents = (
        _content(facility_id, f"older-{uuid4()}", generated),
        _content(facility_id, f"newer-{uuid4()}", generated + timedelta(hours=1)),
    )
    barrier = Barrier(2)

    def publish(content: PublicationContent) -> PublicationResult:
        with sessions() as db:
            barrier.wait()
            return PredictionService(
                db,
                ChargingPredictionReader(db),
                DatasetPredictionReader(db),
            ).publish(content=content, publisher=publisher)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(publish, contents))

    assert len({result.publication.id for result in results}) == 2
    equal_time = generated + timedelta(hours=2)
    equal_contents = (
        _content(facility_id, f"equal-a-{uuid4()}", equal_time),
        _content(facility_id, f"equal-b-{uuid4()}", equal_time),
    )
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        equal_results = list(executor.map(publish, equal_contents))

    assert len({result.publication.id for result in equal_results}) == 2
    assert sum(result.is_current for result in equal_results) == 1
    with sessions() as db:
        current = db.scalar(
            select(WeeklyOccupancyPredictionPublicationModel)
            .join(
                WeeklyOccupancyPredictionCurrentModel,
                WeeklyOccupancyPredictionCurrentModel.publication_id
                == WeeklyOccupancyPredictionPublicationModel.id,
            )
            .where(WeeklyOccupancyPredictionCurrentModel.facility_id == facility_id)
        )
        assert current is not None
        assert current.generated_at == equal_time
        assert current.id in {result.publication.id for result in equal_results}
        assert (
            db.scalar(
                select(func.count())
                .select_from(WeeklyOccupancyPredictionPublicationModel)
                .where(WeeklyOccupancyPredictionPublicationModel.facility_id == facility_id)
            )
            == 4
        )
    engine.dispose()
