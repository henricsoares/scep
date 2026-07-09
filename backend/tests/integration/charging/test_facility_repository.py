from collections.abc import Iterator

import pytest
from app.infrastructure.database import Base
from app.modules.charging.domain.facility import Facility, FacilityStatus, FacilityType
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        yield db
    Base.metadata.drop_all(engine)


def make_facility(name: str = "North Campus") -> Facility:
    return Facility.create(
        name=name,
        facility_type=FacilityType.UNIVERSITY,
        timezone="America/New_York",
        country="United States",
        city="New York",
        address="123 Main St",
        latitude=40.0,
        longitude=-73.0,
        operating_hours={"monday": {"opens": "08:00", "closes": "22:00"}},
        status=FacilityStatus.ACTIVE,
    )


def test_repository_crud(session: Session) -> None:
    repository = SqlAlchemyFacilityRepository(session)
    created = repository.add(make_facility())
    assert repository.get(created.id) == created
    assert repository.exists_by_name("North Campus")

    updated = created.update(
        name="South Campus",
        facility_type=FacilityType.COMMERCIAL,
        timezone="America/New_York",
        country="United States",
        city="New York",
        address="456 Main St",
        latitude=None,
        longitude=None,
        operating_hours=None,
        status=FacilityStatus.INACTIVE,
    )
    assert repository.update(updated).name == "South Campus"
    assert len(repository.list()) == 1
