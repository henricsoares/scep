from collections.abc import Iterator
from uuid import UUID

import pytest
from app.infrastructure.database import Base
from app.modules.charging.domain.station import (
    ChargingStation,
    ChargingStationStatus,
    ConnectorStatus,
    ConnectorType,
)
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.charging.test_facility_repository import make_facility


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        yield db
    Base.metadata.drop_all(engine)


def make_station(facility_id: UUID, serial: str = "SN-1") -> ChargingStation:
    return ChargingStation.create(
        facility_id=facility_id,
        name="Station A",
        description=None,
        serial_number=serial,
        manufacturer="SCEP",
        model="SC-50",
        maximum_power_kw=50.0,
        status=ChargingStationStatus.ACTIVE,
        connectors=[(ConnectorType.CCS2, 50.0, ConnectorStatus.AVAILABLE)],
    )


def test_repository_station_connector_crud_and_uniqueness(session: Session) -> None:
    facilities = SqlAlchemyFacilityRepository(session)
    facility = facilities.add(make_facility())
    repo = SqlAlchemyChargingStationRepository(session)
    created = repo.add(make_station(facility.id))
    assert repo.get(created.id) == created
    assert repo.list_by_facility(facility.id)[0].id == created.id
    assert repo.exists_by_serial_number("SN-1")

    with pytest.raises(IntegrityError):
        repo.add(make_station(facility.id))

    updated = created.update(
        name="Station B", description="Updated", status=ChargingStationStatus.INACTIVE
    )
    assert repo.update(updated).status == ChargingStationStatus.INACTIVE

    station_with_connector = updated.add_connector(
        ConnectorType.NACS, 25.0, ConnectorStatus.AVAILABLE
    )
    connector = repo.add_connector(updated.id, station_with_connector.connectors[-1])
    assert repo.get(updated.id) is not None
    assert (
        repo.update_connector(connector.update_status(ConnectorStatus.RESERVED)).status
        == ConnectorStatus.RESERVED
    )


def test_repository_foreign_keys_are_declared(session: Session) -> None:
    station_table = Base.metadata.tables["charging_stations"]
    connector_table = Base.metadata.tables["connectors"]
    assert station_table.c.facility_id.foreign_keys
    assert connector_table.c.charging_station_id.foreign_keys
