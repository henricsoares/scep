from uuid import uuid4

import pytest
from app.modules.charging.domain.station import (
    ChargingStation,
    ChargingStationStatus,
    ConnectorStatus,
    ConnectorType,
)


def connector_spec() -> list[tuple[ConnectorType, float, ConnectorStatus]]:
    return [(ConnectorType.CCS2, 50.0, ConnectorStatus.AVAILABLE)]


def make_station(status: ChargingStationStatus = ChargingStationStatus.ACTIVE) -> ChargingStation:
    return ChargingStation.create(
        facility_id=uuid4(),
        name="Station A",
        description=None,
        serial_number="SN-1",
        manufacturer="Maker",
        model="M1",
        maximum_power_kw=50.0,
        status=status,
        connectors=connector_spec(),
    )


def test_station_creation_requires_connector_and_valid_values() -> None:
    station = make_station()
    assert len(station.connectors) == 1
    assert station.is_operationally_available()
    with pytest.raises(ValueError, match="connector"):
        ChargingStation.create(
            facility_id=uuid4(),
            name="Station B",
            description=None,
            serial_number="SN-2",
            manufacturer=None,
            model=None,
            maximum_power_kw=10,
            connectors=[],
        )
    with pytest.raises(ValueError, match="name"):
        ChargingStation.create(
            facility_id=uuid4(),
            name="",
            description=None,
            serial_number="SN-2",
            manufacturer=None,
            model=None,
            maximum_power_kw=10,
            connectors=connector_spec(),
        )
    with pytest.raises(ValueError, match="serial_number"):
        ChargingStation.create(
            facility_id=uuid4(),
            name="Station B",
            description=None,
            serial_number="",
            manufacturer=None,
            model=None,
            maximum_power_kw=10,
            connectors=connector_spec(),
        )
    with pytest.raises(ValueError, match="greater than zero"):
        ChargingStation.create(
            facility_id=uuid4(),
            name="Station B",
            description=None,
            serial_number="SN-2",
            manufacturer=None,
            model=None,
            maximum_power_kw=0,
            connectors=connector_spec(),
        )


def test_connector_validation_status_update_and_station_gate() -> None:
    station = make_station(ChargingStationStatus.INACTIVE)
    assert not station.is_operationally_available()
    connector = station.connectors[0]
    assert (
        connector.update_status(ConnectorStatus.OUT_OF_SERVICE).status
        == ConnectorStatus.OUT_OF_SERVICE
    )
    assert (
        station.update(
            name="Station A", description="maint", status=ChargingStationStatus.UNDER_MAINTENANCE
        )
        .connectors[0]
        .status
        == ConnectorStatus.AVAILABLE
    )
    with pytest.raises(ValueError, match="connector maximum_power_kw"):
        make_station().add_connector(ConnectorType.NACS, 0, ConnectorStatus.AVAILABLE)


def test_facility_ownership_is_immutable() -> None:
    station = make_station()
    updated = station.update(name="Renamed", description=None, status=ChargingStationStatus.ACTIVE)
    assert updated.facility_id == station.facility_id
