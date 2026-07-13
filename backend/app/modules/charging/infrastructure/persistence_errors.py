from dataclasses import dataclass

from sqlalchemy.exc import DBAPIError

EXCLUSION_VIOLATION = "23P01"
DEADLOCK_DETECTED = "40P01"
SERIALIZATION_FAILURE = "40001"

CONSTRAINT_CONFLICT_CODES = {
    "reservations_connector_no_overlap": "CONNECTOR_RESERVATION_CONFLICT",
    "reservations_vehicle_no_overlap": "VEHICLE_RESERVATION_CONFLICT",
}


@dataclass(frozen=True)
class ReservationCalendarWriteConflict(Exception):
    code: str | None
    sqlstate: str


def classify_reservation_calendar_write(
    exc: DBAPIError,
) -> ReservationCalendarWriteConflict | None:
    original = exc.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate == EXCLUSION_VIOLATION:
        diagnostic = getattr(original, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if not isinstance(constraint_name, str):
            return None
        code = CONSTRAINT_CONFLICT_CODES.get(constraint_name)
        return None if code is None else ReservationCalendarWriteConflict(code, sqlstate)
    if sqlstate in {DEADLOCK_DETECTED, SERIALIZATION_FAILURE}:
        return ReservationCalendarWriteConflict(None, sqlstate)
    return None
