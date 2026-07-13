from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import Mock
from uuid import uuid4

import pytest
from app.modules.charging.application.reservation_service import ReservationService
from app.modules.charging.domain.reservation import Reservation
from app.modules.charging.infrastructure.persistence_errors import (
    DEADLOCK_DETECTED,
    EXCLUSION_VIOLATION,
    SERIALIZATION_FAILURE,
    ReservationCalendarWriteConflict,
    classify_reservation_calendar_write,
)
from app.modules.charging.infrastructure.reservation_repository import (
    SqlAlchemyReservationRepository,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


@dataclass
class Diagnostic:
    constraint_name: str | None


class OriginalDatabaseError(Exception):
    def __init__(self, sqlstate: str | None, constraint_name: str | None = None) -> None:
        super().__init__("database operation failed")
        self.sqlstate = sqlstate
        self.diag = Diagnostic(constraint_name)


def database_error(sqlstate: str | None, constraint_name: str | None = None) -> DBAPIError:
    return DBAPIError(
        "redacted statement",
        {},
        OriginalDatabaseError(sqlstate, constraint_name),
        False,
    )


@pytest.mark.parametrize(
    ("constraint_name", "expected_code"),
    [
        ("reservations_connector_no_overlap", "CONNECTOR_RESERVATION_CONFLICT"),
        ("reservations_vehicle_no_overlap", "VEHICLE_RESERVATION_CONFLICT"),
    ],
)
def test_classifies_known_exclusion_constraints(constraint_name: str, expected_code: str) -> None:
    conflict = classify_reservation_calendar_write(
        database_error(EXCLUSION_VIOLATION, constraint_name)
    )
    assert conflict is not None
    assert conflict.code == expected_code
    assert conflict.sqlstate == EXCLUSION_VIOLATION


@pytest.mark.parametrize("sqlstate", [DEADLOCK_DETECTED, SERIALIZATION_FAILURE])
def test_classifies_calendar_write_races(sqlstate: str) -> None:
    conflict = classify_reservation_calendar_write(database_error(sqlstate))
    assert conflict is not None
    assert conflict.code is None
    assert conflict.sqlstate == sqlstate


@pytest.mark.parametrize(
    ("sqlstate", "constraint_name"),
    [
        (None, None),
        ("08006", None),
        ("23503", None),
        (EXCLUSION_VIOLATION, "some_unrelated_exclusion_constraint"),
    ],
)
def test_does_not_classify_unrelated_database_failures(
    sqlstate: str | None, constraint_name: str | None
) -> None:
    assert classify_reservation_calendar_write(database_error(sqlstate, constraint_name)) is None


def test_repository_reraises_unrelated_database_failure() -> None:
    session = Mock(spec=Session)
    error = database_error("08006")
    session.commit.side_effect = error
    now = datetime.now(UTC)
    reservation = Reservation.create(
        owner_id=uuid4(),
        vehicle_id=uuid4(),
        connector_id=uuid4(),
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        now=now,
    )

    with pytest.raises(DBAPIError) as raised:
        SqlAlchemyReservationRepository(session).add(reservation)

    assert raised.value is error
    session.rollback.assert_called_once_with()


def test_recognized_calendar_race_has_stable_fallback_contract() -> None:
    reservations = Mock()
    reservations.find_conflict.return_value = None
    service = ReservationService(
        cast(Any, reservations),
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
    )
    start = datetime.now(UTC) + timedelta(hours=1)

    conflict = service._race_conflict(
        ReservationCalendarWriteConflict(None, DEADLOCK_DETECTED),
        connector_id=uuid4(),
        vehicle_id=uuid4(),
        start_at=start,
        end_at=start + timedelta(hours=1),
    )

    assert conflict.code == "RESERVATION_CALENDAR_CONFLICT"
